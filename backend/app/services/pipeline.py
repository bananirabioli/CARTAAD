"""Post-capture pipeline hook: every new capture opens a case and runs classification, interpretation,
strategy suggestion and risk score. Human decision comes next."""

from sqlalchemy.orm import Session

from app.models.core import User
from app.models.monitoring import Post


def process_post(db: Session, post: Post, user: User | None = None) -> None:
    from app.services.cases import process_new_post

    process_new_post(db, post, user)
