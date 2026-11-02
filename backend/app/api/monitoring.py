"""Monitoreo (6.1): fuentes, publicaciones, snapshots, captura manual, importación, webhook y cuentas propias."""

import base64
import csv
import io
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.adapters.sources import FileImportAdapter
from app.api.deps import Ctx, get_ctx, owned, require
from app.config import get_settings
from app.db import get_db, utcnow
from app.errors import AppError, invalid, not_found
from app.models.core import Client
from app.models.monitoring import MonitoredSource, OwnedAccount, Post
from app.models.styles import Format
from app.schemas.common import Page
from app.schemas.monitoring import (
    AccountIn,
    AccountOut,
    AccountPatch,
    CheckResult,
    ImportReport,
    PostDetail,
    PostOut,
    SnapshotIn,
    SourceIn,
    SourceOut,
    SourcePatch,
    WebhookIn,
)
from app.services import audit
from app.services.alert import add_snapshot, apply_alert, baseline_sufficient
from app.services.capture import capture_manual
from app.services.ingest import run_source, store_post

logger = logging.getLogger("uvicorn.error")  # shows up in `docker compose logs api`
router = APIRouter(tags=["monitoring"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024


# ------------------------------------------------------------------ sources


def _source_out(ctx: Ctx, s: MonitoredSource) -> SourceOut:
    count = ctx.db.scalar(select(func.count()).where(Post.source_id == s.id, Post.is_history.is_(False))) or 0
    return SourceOut.model_validate(s).model_copy(update={"baseline_ok": baseline_sufficient(s, ctx.settings), "posts_count": count})


@router.get("/sources", response_model=Page[SourceOut])
def list_sources(
    ctx: Ctx = Depends(get_ctx),
    q: str | None = None,
    network: str | None = None,
    source_type: str | None = None,
    priority: str | None = None,
    active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[SourceOut]:
    stmt = select(MonitoredSource).where(MonitoredSource.client_id == ctx.client_id)
    if q:
        stmt = stmt.where(or_(MonitoredSource.name.ilike(f"%{q}%"), MonitoredSource.handle.ilike(f"%{q}%")))
    if network:
        stmt = stmt.where(MonitoredSource.network == network)
    if source_type:
        stmt = stmt.where(MonitoredSource.source_type == source_type)
    if priority:
        stmt = stmt.where(MonitoredSource.priority == priority)
    if active is not None:
        stmt = stmt.where(MonitoredSource.active.is_(active))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    order = {"alta": 0, "media": 1, "baja": 2}
    rows = list(ctx.db.scalars(stmt.order_by(MonitoredSource.name).offset((page - 1) * page_size).limit(page_size)))
    rows.sort(key=lambda s: (not s.active, order.get(s.priority, 3), s.name))
    return Page(items=[_source_out(ctx, s) for s in rows], total=total, page=page, page_size=page_size)


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: int, ctx: Ctx = Depends(get_ctx)) -> SourceOut:
    return _source_out(ctx, owned(ctx.db, MonitoredSource, source_id, ctx.client_id))


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(body: SourceIn, ctx: Ctx = Depends(require("sources.manage"))) -> SourceOut:
    s = MonitoredSource(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(s)
    ctx.db.flush()
    audit.record(ctx.db, action="source.create", entity_type="source", entity_id=s.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(s))
    ctx.db.commit()
    return _source_out(ctx, s)


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourcePatch, ctx: Ctx = Depends(require("sources.manage"))) -> SourceOut:
    s = owned(ctx.db, MonitoredSource, source_id, ctx.client_id)
    before = audit.snapshot(s)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    audit.record(ctx.db, action="source.update", entity_type="source", entity_id=s.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(s))
    ctx.db.commit()
    return _source_out(ctx, s)


@router.post("/sources/import", response_model=ImportReport)
async def import_sources(file: UploadFile = File(...), ctx: Ctx = Depends(require("sources.manage"))) -> ImportReport:
    """CSV columns: name, network, handle, url, source_type, priority, active, check_frequency_minutes, notes."""
    text = (await file.read()).decode("utf-8-sig")
    created = updated = 0
    errors = []
    for line, row in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        try:
            body = SourceIn(
                name=row.get("name", "").strip(), network=(row.get("network") or "facebook").strip(), handle=(row.get("handle") or "").strip(),
                url=(row.get("url") or "").strip() or None, source_type=(row.get("source_type") or "pagina_ciudadana").strip(),
                priority=(row.get("priority") or "media").strip(), active=(row.get("active") or "true").strip().lower() not in ("false", "0", "no"),
                check_frequency_minutes=int(row.get("check_frequency_minutes") or 60), notes=(row.get("notes") or "").strip(),
            )
        except (ValueError, TypeError) as exc:
            errors.append({"line": line, "error": str(exc)[:200]})
            continue
        existing = ctx.db.scalar(select(MonitoredSource).where(MonitoredSource.client_id == ctx.client_id, MonitoredSource.name == body.name, MonitoredSource.network == body.network))
        if existing:
            for k, v in body.model_dump().items():
                setattr(existing, k, v)
            updated += 1
        else:
            ctx.db.add(MonitoredSource(client_id=ctx.client_id, **body.model_dump()))
            created += 1
    audit.record(ctx.db, action="source.import", entity_type="source", client_id=ctx.client_id, user=ctx.user, after={"created": created, "updated": updated, "errors": len(errors)}, note=file.filename or "")
    ctx.db.commit()
    return ImportReport(created=created, updated=updated, errors=errors)


@router.post("/sources/{source_id}/check", response_model=CheckResult)
def check_source(source_id: int, ctx: Ctx = Depends(require("case.capture"))) -> dict:
    s = owned(ctx.db, MonitoredSource, source_id, ctx.client_id)
    result = run_source(ctx.db, s, user=ctx.user)
    ctx.db.commit()
    return result


# ------------------------------------------------------------------ posts


def _case_ref(ctx: Ctx, post: Post) -> tuple[int | None, str | None]:
    try:
        from app.models.cases import Case
    except ImportError:  # pragma: no cover - before M4
        return None, None
    case = ctx.db.scalar(select(Case).where(Case.post_id == post.id))
    return (case.id, case.code) if case else (None, None)


def _post_out(ctx: Ctx, post: Post, model: type[PostOut] = PostOut) -> PostOut:
    case_id, case_code = _case_ref(ctx, post)
    extra = {"source_name": post.source.name if post.source else None, "source_type": post.source.source_type if post.source else None, "case_id": case_id, "case_code": case_code}
    if model is PostDetail:
        extra.update(snapshots=list(post.snapshots), comments=list(post.comments), baseline_per_hour=post.source.baseline_per_hour if post.source else None)
    return model.model_validate(post).model_copy(update=extra)


@router.get("/posts", response_model=Page[PostOut])
def list_posts(
    ctx: Ctx = Depends(get_ctx),
    q: str | None = None,
    source_id: int | None = None,
    alert_level: str | None = None,
    origin: str | None = None,
    network: str | None = None,
    since: datetime | None = None,
    order: str = Query("recent", pattern="^(recent|velocity|ratio)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[PostOut]:
    stmt = select(Post).where(Post.client_id == ctx.client_id, Post.is_history.is_(False))
    if q:
        stmt = stmt.where(Post.text.ilike(f"%{q}%"))
    if source_id:
        stmt = stmt.where(Post.source_id == source_id)
    if alert_level:
        stmt = stmt.where(Post.alert_level == alert_level)
    if origin:
        stmt = stmt.where(Post.origin == origin)
    if network:
        stmt = stmt.where(Post.network == network)
    if since:
        stmt = stmt.where(Post.published_at >= since)
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    ordering = {"recent": Post.published_at.desc(), "velocity": Post.velocity.desc(), "ratio": Post.alert_ratio.desc()}[order]
    rows = ctx.db.scalars(stmt.order_by(ordering.nulls_last()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[_post_out(ctx, p) for p in rows], total=total, page=page, page_size=page_size)


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(post_id: int, ctx: Ctx = Depends(get_ctx)) -> PostOut:
    return _post_out(ctx, owned(ctx.db, Post, post_id, ctx.client_id), PostDetail)


@router.post("/posts/{post_id}/snapshots", response_model=PostDetail)
def add_post_snapshot(post_id: int, body: SnapshotIn, ctx: Ctx = Depends(require("case.capture"))) -> PostOut:
    post = owned(ctx.db, Post, post_id, ctx.client_id)
    add_snapshot(ctx.db, post, body.likes, body.comments, body.shares, body.taken_at or utcnow())
    ctx.db.flush()
    result = apply_alert(post, ctx.settings)
    audit.record(ctx.db, action="post.snapshot", entity_type="post", entity_id=post.id, client_id=ctx.client_id, user=ctx.user, after=body.model_dump(mode="json"), note=f"alerta {result.level}")
    ctx.db.commit()
    return _post_out(ctx, post, PostDetail)


@router.post("/posts/manual", response_model=PostDetail, status_code=201)
async def manual_capture(
    text: str = Form(""),
    network: str = Form("facebook"),
    url: str | None = Form(None),
    source_id: int | None = Form(None),
    source_name: str | None = Form(None),
    source_type: str | None = Form(None),
    blur_names: bool = Form(False),
    published_at: datetime | None = Form(None),
    likes: int | None = Form(None),
    comments: int | None = Form(None),
    shares: int | None = Form(None),
    comments_text: str = Form(""),
    image: UploadFile | None = File(None),
    ctx: Ctx = Depends(require("case.capture")),
) -> PostOut:
    data = None
    if image is not None:  # pasted images can arrive without a filename
        data = await image.read() or None
        if data and image.content_type not in ("image/png", "image/jpeg", "image/webp", "application/octet-stream"):
            raise invalid("la captura debe ser PNG, JPG o WEBP")
        if data and len(data) > MAX_IMAGE_BYTES:
            raise invalid("la imagen excede 8 MB")
    logger.info("manual capture: text=%d chars, image=%s bytes (%s, %r)", len(text or ""), len(data) if data else 0, image.content_type if image else None, image.filename if image else None)
    post = capture_manual(
        ctx.db, ctx.client, ctx.user, text=text, network=network, image=data, url=url, source_id=source_id, source_name=source_name, source_type=source_type,
        blur=blur_names, published_at=published_at, likes=likes, comments=comments, shares=shares,
        comments_text=[c.strip() for c in comments_text.split("\n") if c.strip()],
    )
    ctx.db.commit()
    return _post_out(ctx, post, PostDetail)


@router.post("/posts/import", response_model=ImportReport)
async def import_posts(file: UploadFile = File(...), ctx: Ctx = Depends(require("case.capture"))) -> ImportReport:
    """FileImportAdapter: CSV/JSON export from a listening tool. Rows are matched to sources by handle or name."""
    adapter = FileImportAdapter(await file.read(), file.filename or "")
    sources = list(ctx.db.scalars(select(MonitoredSource).where(MonitoredSource.client_id == ctx.client_id)))
    matched: set[int] = set()
    created = updated = 0
    for source in sources:
        for i, row in enumerate(adapter.rows):
            if row in adapter.rows_for(source):
                matched.add(i)
                _, was_created = store_post(ctx.db, ctx.client, adapter.to_raw(row, source.network), source=source, user=ctx.user)
                created += int(was_created)
                updated += int(not was_created)
    errors = [{"line": i + 2, "error": f"fuente no encontrada: {r.get('source')}"} for i, r in enumerate(adapter.rows) if i not in matched]
    audit.record(ctx.db, action="post.import", entity_type="post", client_id=ctx.client_id, user=ctx.user, after={"created": created, "updated": updated, "errors": len(errors)}, note=file.filename or "")
    ctx.db.commit()
    return ImportReport(created=created, updated=updated, errors=errors)


@router.post("/ingest/webhook", status_code=202, response_model=dict[str, str])
def ingest_webhook(body: WebhookIn, x_webhook_token: str | None = Header(None), db: Session = Depends(get_db)) -> dict[str, str]:
    """Future entry point for a WhatsApp/Telegram bot that forwards captures (stub).

    Requires WEBHOOK_TOKEN. Sender identities are never stored (HR-03): `extra` is discarded.
    """
    token = get_settings().webhook_token
    if not token:
        raise AppError(503, "webhook_disabled", "El webhook no está configurado (WEBHOOK_TOKEN).")
    if x_webhook_token != token:
        raise AppError(401, "not_authenticated")
    client = db.scalar(select(Client).where(Client.slug == body.client_slug))
    if not client:
        raise not_found()
    image = base64.b64decode(body.image_base64) if body.image_base64 else None
    post = capture_manual(db, client, None, text=body.text, network=body.network, image=image, url=body.url, blur=True)
    audit.record(db, action="post.webhook", entity_type="post", entity_id=post.id, client_id=client.id, note=body.channel)
    db.commit()
    return {"status": "recibido", "post_id": str(post.id)}


# ------------------------------------------------------------------ owned accounts


def _check_account_refs(ctx: Ctx, format_slug: str | None) -> None:
    if format_slug and not ctx.db.scalar(select(Format).where(Format.client_id == ctx.client_id, Format.slug == format_slug)):
        raise invalid(f"formato desconocido: {format_slug}")


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(ctx: Ctx = Depends(get_ctx), account_type: str | None = None) -> list[OwnedAccount]:
    stmt = select(OwnedAccount).where(OwnedAccount.client_id == ctx.client_id)
    if account_type:
        stmt = stmt.where(OwnedAccount.account_type == account_type)
    return list(ctx.db.scalars(stmt.order_by(OwnedAccount.account_type, OwnedAccount.display_name)))


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, ctx: Ctx = Depends(require("config.manage"))) -> OwnedAccount:
    _check_account_refs(ctx, body.format_slug)
    acc = OwnedAccount(client_id=ctx.client_id, verified=False, **body.model_dump())
    ctx.db.add(acc)
    ctx.db.flush()
    audit.record(ctx.db, action="account.create", entity_type="account", entity_id=acc.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(acc))
    ctx.db.commit()
    return acc


@router.patch("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountPatch, ctx: Ctx = Depends(require("config.manage"))) -> OwnedAccount:
    acc = owned(ctx.db, OwnedAccount, account_id, ctx.client_id)
    data = body.model_dump(exclude_unset=True)
    _check_account_refs(ctx, data.get("format_slug"))
    before = audit.snapshot(acc)
    for k, v in data.items():
        setattr(acc, k, v)
    if "registered" in data and not acc.registered:
        acc.verified, acc.verified_at = False, None
    audit.record(ctx.db, action="account.update", entity_type="account", entity_id=acc.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(acc))
    ctx.db.commit()
    return acc


@router.post("/accounts/{account_id}/verify", response_model=AccountOut)
def verify_account(account_id: int, ctx: Ctx = Depends(require("config.manage"))) -> OwnedAccount:
    acc = owned(ctx.db, OwnedAccount, account_id, ctx.client_id)
    if not acc.registered:
        raise invalid("primero registra la cuenta")
    acc.verified, acc.verified_by_id, acc.verified_at = True, ctx.user.id, utcnow()
    audit.record(ctx.db, action="account.verify", entity_type="account", entity_id=acc.id, client_id=ctx.client_id, user=ctx.user)
    ctx.db.commit()
    return acc
