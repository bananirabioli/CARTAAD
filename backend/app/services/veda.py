"""Modo veda (HR-04): manual restrictions per client and date range."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.guardrails.hard_rules import restriction_active
from app.models.ops import RestrictionMode


def restrictions(db: Session, client_id: int) -> list[RestrictionMode]:
    return list(db.scalars(select(RestrictionMode).where(RestrictionMode.client_id == client_id).order_by(RestrictionMode.starts_at)))


def active_restriction(db: Session, client_id: int, when: datetime | None = None) -> RestrictionMode | None:
    when = when or utcnow()
    return next((r for r in restrictions(db, client_id) if restriction_active(r, when)), None)


def overlapping_restrictions(db: Session, client_id: int, start: datetime | None, end: datetime | None) -> list[RestrictionMode]:
    """Enabled restrictions whose window intersects [start, end] (open ends = unbounded)."""
    out = []
    for r in restrictions(db, client_id):
        if not r.active:
            continue
        r_start, r_end = r.starts_at, r.ends_at
        if (end is None or r_start is None or r_start <= end) and (start is None or r_end is None or start <= r_end):
            out.append(r)
    return out
