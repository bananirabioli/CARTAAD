"""Post-capture pipeline hook. M4 plugs classification, interpretation and case creation here."""

from sqlalchemy.orm import Session

from app.models.core import User
from app.models.monitoring import Post


def process_post(db: Session, post: Post, user: User | None = None) -> None:
    """Called after every new capture (automatic or manual)."""
    return None
