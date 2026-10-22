"""Run the capture pipeline over the seeded posts: every post becomes a classified and interpreted case."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cases import Case
from app.models.core import Client
from app.models.monitoring import Post
from app.services.cases import process_new_post


def seed_cases(db: Session, clients: dict[str, Client]) -> None:
    for client in clients.values():
        if db.scalar(select(Case.id).where(Case.client_id == client.id).limit(1)):
            continue
        posts = db.scalars(select(Post).where(Post.client_id == client.id, Post.is_history.is_(False)).order_by(Post.published_at, Post.id))
        for post in posts:
            process_new_post(db, post)
        db.flush()
