from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Ctx, accessible_client_ids, current_user, get_ctx, resolve_client, user_permissions
from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models.core import Client, User
from app.schemas.common import Message
from app.schemas.core import ClientOut, LoginIn, MeOut, SelectClientIn, UserOut, ViewAsIn
from app.services import audit
from app.services.security import CLIENT_COOKIE, SESSION_COOKIE, make_session_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session(response: Response, user: User) -> None:
    s = get_settings()
    response.set_cookie(
        SESSION_COOKIE, make_session_token(user.id), max_age=s.session_max_age, httponly=True, samesite="lax", secure=s.cookie_secure
    )


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not user.active or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials")
    _set_session(response, user)
    audit.record(db, action="auth.login", entity_type="user", entity_id=user.id, user=user)
    db.commit()
    return user


@router.post("/logout", response_model=Message)
def logout(response: Response) -> Message:
    response.delete_cookie(SESSION_COOKIE)
    return Message()


@router.get("/me", response_model=MeOut)
def me(ctx: Ctx = Depends(get_ctx)) -> MeOut:
    from app.services.reminders import active_restriction_summary, reminders_for

    ids = accessible_client_ids(ctx.db, ctx.user)
    clients = list(ctx.db.scalars(select(Client).where(Client.id.in_(ids)).order_by(Client.id)))
    return MeOut(
        user=UserOut.model_validate(ctx.user),
        client=ClientOut.model_validate(ctx.client),
        clients=[ClientOut.model_validate(c) for c in clients],
        permissions=user_permissions(ctx.user),
        demo_mode=get_settings().demo_mode,
        llm_provider=get_settings().llm_provider,
        restriction=active_restriction_summary(ctx.db, ctx.client),
        reminders=reminders_for(ctx),
    )


@router.post("/select-client", response_model=ClientOut)
def select_client(body: SelectClientIn, request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Client:
    if body.client_id not in accessible_client_ids(db, user):
        raise AppError(403, "client_forbidden")
    client = db.get(Client, body.client_id)
    response.set_cookie(CLIENT_COOKIE, str(body.client_id), max_age=get_settings().session_max_age, samesite="lax")
    return client


@router.get("/demo-users", response_model=list[UserOut])
def demo_users(db: Session = Depends(get_db)) -> list[User]:
    if not get_settings().demo_mode:
        raise AppError(403, "demo_only")
    return list(db.scalars(select(User).where(User.is_demo.is_(True), User.active.is_(True)).order_by(User.id)))


@router.post("/view-as", response_model=UserOut)
def view_as(body: ViewAsIn, request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(current_user)) -> User:
    """Demo mode: switch the session to the demo user that holds `role` (and the kb_owner flag)."""
    if not get_settings().demo_mode:
        raise AppError(403, "demo_only")
    target = db.scalar(
        select(User).where(User.is_demo.is_(True), User.role == body.role, User.kb_owner.is_(body.kb_owner), User.active.is_(True))
    )
    if not target:
        raise AppError(404, "demo_user_missing", role=body.role)
    client = resolve_client(request, db, user)
    if client.id not in accessible_client_ids(db, target):
        raise AppError(403, "client_forbidden")
    _set_session(response, target)
    audit.record(db, action="auth.view_as", entity_type="user", entity_id=target.id, client_id=client.id, user=user, note=f"→ {target.email}")
    db.commit()
    return target
