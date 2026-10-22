from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.core import AuditLog, User

_SKIP = {"password_hash", "embedding"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(v) for v in value]
    return value


def snapshot(obj: Any, fields: list[str] | None = None) -> dict[str, Any]:
    """Column values of an ORM object, JSON-safe, for before/after audit entries."""
    if obj is None:
        return {}
    mapper = inspect(obj).mapper
    names = fields or [c.key for c in mapper.column_attrs]
    return {n: _jsonable(getattr(obj, n)) for n in names if n not in _SKIP}


def diff_snapshots(before: dict[str, Any], after: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    keys = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
    return {k: before.get(k) for k in keys}, {k: after.get(k) for k in keys}


def record(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Any = None,
    client_id: int | None = None,
    user: User | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    note: str = "",
    only_changes: bool = True,
) -> AuditLog:
    if only_changes and before is not None and after is not None:
        before, after = diff_snapshots(before, after)
    entry = AuditLog(
        client_id=client_id,
        user_id=user.id if user else None,
        user_label=f"{user.name} ({user.role})" if user else "sistema",
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        before=_jsonable(before) if before is not None else None,
        after=_jsonable(after) if after is not None else None,
        note=note,
    )
    db.add(entry)
    return entry
