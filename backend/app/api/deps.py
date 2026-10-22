from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models.core import Client, Sequence, User, UserClient
from app.services.client_settings import ClientSettings, get_client_settings
from app.services.permissions import has_permission, permissions_for
from app.services.security import CLIENT_COOKIE, SESSION_COOKIE, read_session_token


@dataclass
class Ctx:
    db: Session
    user: User
    client: Client

    @property
    def client_id(self) -> int:
        return self.client.id

    @property
    def settings(self) -> ClientSettings:
        return get_client_settings(self.client)

    def can(self, permission: str) -> bool:
        return has_permission(self.user, permission)

    def require(self, permission: str) -> None:
        if not self.can(permission):
            raise AppError(403, "forbidden", permission=permission)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    uid = read_session_token(request.cookies.get(SESSION_COOKIE))
    user = db.get(User, uid) if uid else None
    if not user or not user.active:
        raise AppError(401, "not_authenticated")
    return user


def accessible_client_ids(db: Session, user: User) -> list[int]:
    if user.role == "admin":
        return list(db.scalars(select(Client.id).order_by(Client.id)))
    return list(db.scalars(select(UserClient.client_id).where(UserClient.user_id == user.id).order_by(UserClient.client_id)))


def resolve_client(request: Request, db: Session, user: User) -> Client:
    raw = request.headers.get("x-client-id") or request.cookies.get(CLIENT_COOKIE)
    allowed = accessible_client_ids(db, user)
    if not allowed:
        raise AppError(403, "client_forbidden")
    if raw is None:
        client_id = allowed[0]
    else:
        try:
            client_id = int(raw)
        except ValueError as exc:
            raise AppError(400, "client_required") from exc
        if client_id not in allowed:
            raise AppError(403, "client_forbidden")
    client = db.get(Client, client_id)
    if client is None:
        raise AppError(403, "client_forbidden")
    return client


def get_ctx(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)) -> Ctx:
    return Ctx(db=db, user=user, client=resolve_client(request, db, user))


def require(permission: str) -> Callable[[Ctx], Ctx]:
    def _dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        ctx.require(permission)
        return ctx

    return _dep


def next_code(db: Session, client_id: int | None, name: str, prefix: str, width: int = 3) -> str:
    seq = db.scalar(select(Sequence).where(Sequence.client_id == client_id, Sequence.name == name).with_for_update())
    if seq is None:
        seq = Sequence(client_id=client_id, name=name, value=0)
        db.add(seq)
    seq.value += 1
    db.flush()
    return f"{prefix}-{seq.value:0{width}d}"


def user_permissions(user: User) -> list[str]:
    return sorted(permissions_for(user))


def owned(db: Session, model: type, obj_id: int, client_id: int):  # noqa: ANN201
    """Fetch a client-scoped row or raise 404 (also when it belongs to another client)."""
    from app.errors import not_found

    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "client_id", None) != client_id:
        raise not_found()
    return obj
