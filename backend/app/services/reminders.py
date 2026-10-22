from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.db import utcnow
from app.i18n import t
from app.models.core import Client

if TYPE_CHECKING:
    from app.api.deps import Ctx


def active_restriction_summary(db: Session, client: Client) -> dict[str, Any] | None:
    from app.services.veda import active_restriction

    r = active_restriction(db, client.id)
    if r is None:
        return None
    return {
        "id": r.id,
        "name": r.name,
        "starts_at": r.starts_at.isoformat() if r.starts_at else None,
        "ends_at": r.ends_at.isoformat() if r.ends_at else None,
        "blocked_formats": r.blocked_formats,
        "blocked_creatives": r.blocked_creatives,
        "mandatory_legends": r.mandatory_legends,
        "reason": r.reason,
    }


def reminders_for(ctx: "Ctx") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if ctx.user.role == "admin":
        s = ctx.settings
        last = datetime.fromisoformat(s.sources_last_reviewed_at) if s.sources_last_reviewed_at else None
        due = last + timedelta(days=s.source_review_interval_days) if last else None
        if due is None or due <= utcnow():
            out.append(
                {
                    "kind": "sources_review",
                    "message": t("reminders.sources_review", days=s.source_review_interval_days),
                    "last_reviewed_at": s.sources_last_reviewed_at,
                }
            )
    return out
