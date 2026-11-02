"""Clients, users, topics, settings, hard rules and audit log."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import Ctx, accessible_client_ids, get_ctx, require
from app.config import get_settings as get_app_settings
from app.errors import AppError, conflict, not_found
from app.guardrails.hard_rules import HARD_RULES
from app.models.core import AuditLog, Client, Topic, User, UserClient
from app.schemas.common import AuditOut, Page
from app.schemas.core import (
    ClientIn,
    ClientOut,
    ClientPatch,
    HardRuleOut,
    SettingsOut,
    SettingsPatch,
    TopicIn,
    TopicOut,
    TopicPatch,
    UserAdminOut,
    UserIn,
    UserPatch,
)
from app.seed.production import ensure_main_account
from app.services import audit
from app.services.bootstrap import bootstrap_client
from app.services.client_settings import get_client_settings, update_client_settings
from app.services.security import hash_password

router = APIRouter(tags=["admin"])


# ------------------------------------------------------------------ clients


@router.get("/clients", response_model=list[ClientOut])
def list_clients(ctx: Ctx = Depends(get_ctx)) -> list[Client]:
    ids = accessible_client_ids(ctx.db, ctx.user)
    return list(ctx.db.scalars(select(Client).where(Client.id.in_(ids)).order_by(Client.id)))


@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(body: ClientIn, ctx: Ctx = Depends(require("config.manage"))) -> Client:
    if ctx.db.scalar(select(Client).where(Client.slug == body.slug)):
        raise conflict(body.slug)
    client = Client(**body.model_dump())
    ctx.db.add(client)
    ctx.db.flush()
    bootstrap_client(ctx.db, client)
    ensure_main_account(ctx.db, client, ctx.user)
    ctx.db.add(UserClient(user_id=ctx.user.id, client_id=client.id))
    audit.record(ctx.db, action="client.create", entity_type="client", entity_id=client.id, client_id=client.id, user=ctx.user, after=audit.snapshot(client))
    ctx.db.commit()
    return client


@router.patch("/clients/{client_id}", response_model=ClientOut)
def update_client(client_id: int, body: ClientPatch, ctx: Ctx = Depends(require("config.manage"))) -> Client:
    if client_id not in accessible_client_ids(ctx.db, ctx.user):
        raise AppError(403, "client_forbidden")
    client = ctx.db.get(Client, client_id)
    before = audit.snapshot(client)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(client, k, v)
    audit.record(ctx.db, action="client.update", entity_type="client", entity_id=client.id, client_id=client.id, user=ctx.user, before=before, after=audit.snapshot(client))
    ctx.db.commit()
    return client


# ------------------------------------------------------------------ settings


@router.get("/settings", response_model=SettingsOut)
def get_settings_(ctx: Ctx = Depends(get_ctx)) -> SettingsOut:
    return SettingsOut(settings=get_client_settings(ctx.client).model_dump())


@router.patch("/settings", response_model=SettingsOut)
def patch_settings(body: SettingsPatch, ctx: Ctx = Depends(require("config.manage"))) -> SettingsOut:
    before = get_client_settings(ctx.client).model_dump()
    try:
        updated = update_client_settings(ctx.client, body.patch)
    except ValueError as exc:
        raise AppError(422, "invalid_value", detail=str(exc)) from exc
    audit.record(ctx.db, action="settings.update", entity_type="client_settings", entity_id=ctx.client_id, client_id=ctx.client_id, user=ctx.user, before=before, after=updated.model_dump())
    ctx.db.commit()
    return SettingsOut(settings=updated.model_dump())


@router.post("/settings/sources-reviewed", response_model=SettingsOut)
def mark_sources_reviewed(ctx: Ctx = Depends(require("sources.manage"))) -> SettingsOut:
    from app.db import utcnow

    updated = update_client_settings(ctx.client, {"sources_last_reviewed_at": utcnow().isoformat()})
    audit.record(ctx.db, action="sources.reviewed", entity_type="client_settings", entity_id=ctx.client_id, client_id=ctx.client_id, user=ctx.user)
    ctx.db.commit()
    return SettingsOut(settings=updated.model_dump())


# ------------------------------------------------------------------ topics


@router.get("/topics", response_model=list[TopicOut])
def list_topics(ctx: Ctx = Depends(get_ctx)) -> list[Topic]:
    return list(ctx.db.scalars(select(Topic).where(Topic.client_id == ctx.client_id).order_by(Topic.name)))


@router.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(body: TopicIn, ctx: Ctx = Depends(require("catalog.manage"))) -> Topic:
    if ctx.db.scalar(select(Topic).where(Topic.client_id == ctx.client_id, Topic.slug == body.slug)):
        raise conflict(body.slug)
    topic = Topic(client_id=ctx.client_id, **body.model_dump())
    ctx.db.add(topic)
    ctx.db.flush()
    audit.record(ctx.db, action="topic.create", entity_type="topic", entity_id=topic.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(topic))
    ctx.db.commit()
    return topic


@router.patch("/topics/{topic_id}", response_model=TopicOut)
def update_topic(topic_id: int, body: TopicPatch, ctx: Ctx = Depends(require("catalog.manage"))) -> Topic:
    topic = ctx.db.get(Topic, topic_id)
    if not topic or topic.client_id != ctx.client_id:
        raise not_found()
    before = audit.snapshot(topic)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(topic, k, v)
    audit.record(ctx.db, action="topic.update", entity_type="topic", entity_id=topic.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(topic))
    ctx.db.commit()
    return topic


# ------------------------------------------------------------------ users


def _user_out(db, user: User) -> UserAdminOut:  # noqa: ANN001
    ids = list(db.scalars(select(UserClient.client_id).where(UserClient.user_id == user.id)))
    return UserAdminOut.model_validate(user).model_copy(update={"client_ids": ids})


@router.get("/users", response_model=list[UserAdminOut])
def list_users(ctx: Ctx = Depends(require("users.manage"))) -> list[UserAdminOut]:
    users = ctx.db.scalars(
        select(User).join(UserClient, UserClient.user_id == User.id).where(UserClient.client_id == ctx.client_id).order_by(User.id)
    ).unique()
    return [_user_out(ctx.db, u) for u in users]


@router.post("/users", response_model=UserAdminOut, status_code=201)
def create_user(body: UserIn, ctx: Ctx = Depends(require("users.manage"))) -> UserAdminOut:
    email = body.email.lower()
    if ctx.db.scalar(select(User).where(User.email == email)):
        raise conflict(email)
    user = User(email=email, name=body.name, role=body.role, kb_owner=body.kb_owner, password_hash=hash_password(body.password))
    ctx.db.add(user)
    ctx.db.flush()
    allowed = set(accessible_client_ids(ctx.db, ctx.user))
    for cid in set(body.client_ids or [ctx.client_id]) & allowed:
        ctx.db.add(UserClient(user_id=user.id, client_id=cid))
    audit.record(ctx.db, action="user.create", entity_type="user", entity_id=user.id, client_id=ctx.client_id, user=ctx.user, after=audit.snapshot(user))
    ctx.db.commit()
    return _user_out(ctx.db, user)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def update_user(user_id: int, body: UserPatch, ctx: Ctx = Depends(require("users.manage"))) -> UserAdminOut:
    user = ctx.db.get(User, user_id)
    if not user:
        raise not_found()
    before = audit.snapshot(user)
    data = body.model_dump(exclude_unset=True)
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
    client_ids = data.pop("client_ids", None)
    for k, v in data.items():
        setattr(user, k, v)
    if client_ids is not None:
        allowed = set(accessible_client_ids(ctx.db, ctx.user))
        for link in list(user.clients):
            if link.client_id in allowed and link.client_id not in client_ids:
                ctx.db.delete(link)
        current = {link.client_id for link in user.clients}
        for cid in set(client_ids) & allowed - current:
            ctx.db.add(UserClient(user_id=user.id, client_id=cid))
    audit.record(ctx.db, action="user.update", entity_type="user", entity_id=user.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(user))
    ctx.db.commit()
    return _user_out(ctx.db, user)


# ------------------------------------------------------------------ hard rules & audit


@router.get("/meta/ai-status", response_model=dict[str, Any])
def ai_status(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """What the Modelos tab shows: active providers, models and whether the key is set (never the key itself)."""
    s = get_app_settings()
    return {
        "llm_provider": s.llm_provider, "image_provider": s.image_provider, "video_provider": s.video_provider,
        "key_present": bool(s.openrouter_api_key), "models": {"analysis": s.openrouter_model_analysis, "text": s.openrouter_model_text,
                                                              "image": s.openrouter_model_image, "video": s.openrouter_model_video},
        "video_seconds": s.video_max_seconds,
    }


@router.get("/meta/hard-rules", response_model=list[HardRuleOut])
def hard_rules() -> list[HardRuleOut]:
    return [HardRuleOut(id=r.id, title=r.title, description=r.description) for r in HARD_RULES.values()]


@router.get("/audit", response_model=Page[AuditOut])
def list_audit(
    ctx: Ctx = Depends(get_ctx),
    entity_type: str | None = None,
    entity_id: str | None = None,
    action: str | None = None,
    since: datetime | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[AuditOut]:
    stmt = select(AuditLog).where(AuditLog.client_id == ctx.client_id)
    if not ctx.can("audit.read"):
        stmt = stmt.where(AuditLog.user_id == ctx.user.id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if q:
        stmt = stmt.where(AuditLog.note.ilike(f"%{q}%") | AuditLog.user_label.ilike(f"%{q}%") | AuditLog.action.ilike(f"%{q}%"))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = ctx.db.scalars(stmt.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[AuditOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
