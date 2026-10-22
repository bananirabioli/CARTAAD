"""Bandeja de aprobación (6.6), publicación simulada y paquetes para aliados (6.7), exportación."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Ctx, get_ctx, owned, require
from app.api.generation import piece_out
from app.db import get_db
from app.errors import AppError
from app.models.cases import Case
from app.models.generation import Piece
from app.models.monitoring import OwnedAccount, Post
from app.models.publishing import AllyPackage, AllyShare, ScheduledPost
from app.schemas.common import Message, Page
from app.schemas.generation import PieceOut
from app.services import publishing as pub
from app.services.security import sign_file_key

router = APIRouter(tags=["publishing"])


class InboxItem(PieceOut):
    case_status: str | None = None
    alert_level: str | None = None
    topic_slug: str | None = None
    post_text: str = ""


class ScheduleIn(BaseModel):
    piece_id: int
    account_id: int
    scheduled_at: datetime
    copy_piece_id: int | None = None


class ScheduledOut(BaseModel):
    id: int
    case_id: int
    case_code: str
    piece_id: int
    piece_label: str
    copy_piece_id: int | None
    account_id: int
    account_handle: str
    account_type: str
    scheduled_at: datetime
    status: str
    text: str
    error: str
    published_at: datetime | None
    render: str | None = None


class AllyPackageIn(BaseModel):
    case_id: int
    title: str = Field(min_length=3)
    message: str = ""
    piece_ids: list[int]
    expires_in_days: int = Field(7, ge=1, le=60)


class AllyPackageOut(BaseModel):
    id: int
    case_id: int
    case_code: str
    token: str
    title: str
    message: str
    piece_ids: list[int]
    expires_at: datetime
    revoked: bool
    created_at: datetime
    shares: list[dict] = []


class PublicPiece(BaseModel):
    id: int
    label: str
    kind: str
    images: list[str]
    text: str


class PublicPackage(BaseModel):
    title: str
    message: str
    client_name: str
    suggested_copy: str
    expires_at: datetime
    pieces: list[PublicPiece]
    accounts: list[dict]
    download_url: str


class ShareIn(BaseModel):
    account_id: int
    shared_by_name: str = Field(min_length=2)
    piece_id: int | None = None


# ------------------------------------------------------------------ inbox


@router.get("/inbox", response_model=Page[InboxItem])
def inbox(
    ctx: Ctx = Depends(get_ctx),
    status: str | None = Query(None, description="estado de pieza (coma)"),
    flow: str | None = None,
    alert_level: str | None = None,
    style: str | None = None,
    tag: str | None = None,
    kind: str | None = None,
    case_id: int | None = None,
    legal: str | None = Query(None, pattern="^(pendiente|liberada|bloqueada)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=200),
) -> Page[InboxItem]:
    statuses = status.split(",") if status else ["generado", "bloqueado"]
    stmt = select(Piece).join(Case, Case.id == Piece.case_id).where(Piece.client_id == ctx.client_id, Piece.status.in_(statuses))
    if flow:
        stmt = stmt.where(Piece.flow == flow)
    if alert_level:
        stmt = stmt.where(Case.alert_level == alert_level)
    if style:
        stmt = stmt.where(Piece.style_slug == style)
    if kind:
        stmt = stmt.where(Piece.kind == kind)
    if case_id:
        stmt = stmt.where(Piece.case_id == case_id)
    if legal:
        stmt = stmt.where(Piece.legal_required.is_(True), Piece.legal_status == legal)
    rows = list(ctx.db.scalars(stmt.order_by(Piece.updated_at.desc())))
    if tag:
        rows = [p for p in rows if tag in (p.effective_tags or [])]
    total = len(rows)
    items = []
    for p in rows[(page - 1) * page_size : page * page_size]:
        case = ctx.db.get(Case, p.case_id)
        post = ctx.db.get(Post, case.post_id)
        base = piece_out(ctx, p)
        items.append(InboxItem(**base.model_dump(), case_status=case.status, alert_level=case.alert_level, topic_slug=case.topic_slug, post_text=post.text[:240]))
    return Page(items=items, total=total, page=page, page_size=page_size)


# ------------------------------------------------------------------ scheduling


def _scheduled_out(ctx: Ctx, sp: ScheduledPost) -> ScheduledOut:
    case = ctx.db.get(Case, sp.case_id)
    piece = ctx.db.get(Piece, sp.piece_id)
    acc = ctx.db.get(OwnedAccount, sp.account_id)
    label = piece.creative_slug or f"copy · {piece.style_slug}"
    return ScheduledOut(
        id=sp.id, case_id=sp.case_id, case_code=case.code, piece_id=sp.piece_id, piece_label=label, copy_piece_id=sp.copy_piece_id, account_id=acc.id, account_handle=acc.handle,
        account_type=acc.account_type, scheduled_at=sp.scheduled_at, status=sp.status, text=sp.text, error=sp.error, published_at=sp.published_at,
        render=piece.renders[0] if piece.renders else None,
    )


@router.get("/schedule", response_model=list[ScheduledOut])
def list_schedule(ctx: Ctx = Depends(get_ctx), since: datetime | None = None, until: datetime | None = None, status: str | None = None) -> list[ScheduledOut]:
    stmt = select(ScheduledPost).where(ScheduledPost.client_id == ctx.client_id)
    if since:
        stmt = stmt.where(ScheduledPost.scheduled_at >= since)
    if until:
        stmt = stmt.where(ScheduledPost.scheduled_at <= until)
    if status:
        stmt = stmt.where(ScheduledPost.status == status)
    return [_scheduled_out(ctx, sp) for sp in ctx.db.scalars(stmt.order_by(ScheduledPost.scheduled_at))]


@router.post("/schedule", response_model=ScheduledOut, status_code=201)
def create_schedule(body: ScheduleIn, ctx: Ctx = Depends(require("schedule.manage"))) -> ScheduledOut:
    piece = owned(ctx.db, Piece, body.piece_id, ctx.client_id)
    copy_piece = owned(ctx.db, Piece, body.copy_piece_id, ctx.client_id) if body.copy_piece_id else None
    sp = pub.schedule(ctx.db, ctx.user, ctx.client_id, piece=piece, account_id=body.account_id, scheduled_at=body.scheduled_at, copy_piece=copy_piece)
    ctx.db.commit()
    return _scheduled_out(ctx, sp)


@router.post("/schedule/{sp_id}/cancel", response_model=ScheduledOut)
def cancel_schedule(sp_id: int, ctx: Ctx = Depends(require("schedule.manage"))) -> ScheduledOut:
    sp = owned(ctx.db, ScheduledPost, sp_id, ctx.client_id)
    pub.cancel(ctx.db, sp, ctx.user)
    ctx.db.commit()
    return _scheduled_out(ctx, sp)


@router.post("/schedule/{sp_id}/publish-now", response_model=ScheduledOut)
def publish_now(sp_id: int, ctx: Ctx = Depends(require("schedule.manage"))) -> ScheduledOut:
    """Simulated publication (the prototype never posts to real networks)."""
    sp = owned(ctx.db, ScheduledPost, sp_id, ctx.client_id)
    if sp.status != "programado":
        raise AppError(409, "conflict", detail=sp.status)
    pub.publish(ctx.db, sp, ctx.user)
    ctx.db.commit()
    return _scheduled_out(ctx, sp)


# ------------------------------------------------------------------ export


@router.get("/pieces/{piece_id}/export.zip")
def export_piece(piece_id: int, ctx: Ctx = Depends(require("export.pieces"))) -> Response:
    piece = owned(ctx.db, Piece, piece_id, ctx.client_id)
    if piece.status not in ("aprobado", "programado", "publicado"):
        raise AppError(409, "conflict", detail="solo se exportan piezas aprobadas")
    return Response(pub.export_zip(ctx.db, [piece]), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="pieza-{piece.id}.zip"'})


@router.get("/cases/{case_id}/export.zip")
def export_case(case_id: int, ctx: Ctx = Depends(require("export.pieces"))) -> Response:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    pieces = list(ctx.db.scalars(select(Piece).where(Piece.case_id == case.id, Piece.status.in_(("aprobado", "programado", "publicado")))))
    if not pieces:
        raise AppError(409, "conflict", detail="el caso no tiene piezas aprobadas")
    return Response(pub.export_zip(ctx.db, pieces), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{case.code}.zip"'})


# ------------------------------------------------------------------ ally packages


def _package_out(ctx: Ctx, pkg: AllyPackage) -> AllyPackageOut:
    case = ctx.db.get(Case, pkg.case_id)
    shares = []
    for s in ctx.db.scalars(select(AllyShare).where(AllyShare.package_id == pkg.id).order_by(AllyShare.id.desc())):
        acc = ctx.db.get(OwnedAccount, s.account_id)
        shares.append({"account": acc.handle if acc else "?", "by": s.shared_by_name, "piece_id": s.piece_id, "at": s.created_at.isoformat()})
    return AllyPackageOut(id=pkg.id, case_id=pkg.case_id, case_code=case.code, token=pkg.token, title=pkg.title, message=pkg.message, piece_ids=pkg.piece_ids,
                          expires_at=pkg.expires_at, revoked=pkg.revoked, created_at=pkg.created_at, shares=shares)


@router.get("/ally-packages", response_model=list[AllyPackageOut])
def list_packages(ctx: Ctx = Depends(get_ctx)) -> list[AllyPackageOut]:
    rows = ctx.db.scalars(select(AllyPackage).where(AllyPackage.client_id == ctx.client_id).order_by(AllyPackage.id.desc()))
    return [_package_out(ctx, p) for p in rows]


@router.post("/ally-packages", response_model=AllyPackageOut, status_code=201)
def create_package(body: AllyPackageIn, ctx: Ctx = Depends(require("ally.manage"))) -> AllyPackageOut:
    case = owned(ctx.db, Case, body.case_id, ctx.client_id)
    pkg = pub.create_ally_package(ctx.db, ctx.user, case, title=body.title, message=body.message, piece_ids=body.piece_ids, expires_in_days=body.expires_in_days)
    ctx.db.commit()
    return _package_out(ctx, pkg)


@router.post("/ally-packages/{pkg_id}/revoke", response_model=AllyPackageOut)
def revoke_package(pkg_id: int, ctx: Ctx = Depends(require("ally.manage"))) -> AllyPackageOut:
    pkg = owned(ctx.db, AllyPackage, pkg_id, ctx.client_id)
    pkg.revoked = True
    from app.services import audit

    audit.record(ctx.db, action="ally.revoke", entity_type="ally_package", entity_id=pkg.id, client_id=ctx.client_id, user=ctx.user)
    ctx.db.commit()
    return _package_out(ctx, pkg)


@router.get("/public/ally/{token}", response_model=PublicPackage)
def public_package(token: str, db: Session = Depends(get_db)) -> PublicPackage:
    from app.models.core import Client

    pkg = pub.get_valid_package(db, token)
    pieces = list(db.scalars(select(Piece).where(Piece.id.in_(pkg.piece_ids))))
    accounts = [{"id": a.id, "handle": a.handle, "name": a.display_name, "type": a.account_type}
                for a in db.scalars(select(OwnedAccount).where(OwnedAccount.client_id == pkg.client_id, OwnedAccount.account_type.in_(("aliada", "voceria")), OwnedAccount.registered.is_(True), OwnedAccount.verified.is_(True)))]
    client = db.get(Client, pkg.client_id)
    return PublicPackage(
        title=pkg.title, message=pkg.message, client_name=client.name, suggested_copy=pkg.suggested_copy, expires_at=pkg.expires_at,
        pieces=[PublicPiece(id=p.id, label=p.creative_slug or "copy", kind=p.kind, images=[f"/api/public/files/{sign_file_key(k)}" for k in p.renders or []], text=pub.publication_text(db, p)) for p in pieces],
        accounts=accounts, download_url=f"/api/public/ally/{token}/download.zip",
    )


@router.post("/public/ally/{token}/shared", response_model=Message)
def public_share(token: str, body: ShareIn, db: Session = Depends(get_db)) -> Message:
    pkg = pub.get_valid_package(db, token)
    pub.record_share(db, pkg, account_id=body.account_id, shared_by_name=body.shared_by_name, piece_id=body.piece_id)
    db.commit()
    return Message(message="registrado")


@router.get("/public/ally/{token}/download.zip")
def public_download(token: str, db: Session = Depends(get_db)) -> Response:
    pkg = pub.get_valid_package(db, token)
    pieces = list(db.scalars(select(Piece).where(Piece.id.in_(pkg.piece_ids))))
    return Response(pub.export_zip(db, pieces), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="paquete-{pkg.id}.zip"'})


@router.get("/publishing/stats", response_model=dict[str, int])
def publishing_stats(ctx: Ctx = Depends(get_ctx)) -> dict[str, int]:
    def count(status: str) -> int:
        return ctx.db.scalar(select(func.count()).where(ScheduledPost.client_id == ctx.client_id, ScheduledPost.status == status)) or 0

    return {"programado": count("programado"), "publicado": count("publicado"), "error": count("error"), "cancelado": count("cancelado")}
