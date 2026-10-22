from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb import Actor
from app.textnorm import find_terms


def client_actors(db: Session, client_id: int) -> list[Actor]:
    return list(db.scalars(select(Actor).where(Actor.client_id == client_id)))


def mentioned_actors(actors: list[Actor], text: str, include_own: bool = True) -> list[Actor]:
    found = []
    for actor in actors:
        if not include_own and actor.is_own:
            continue
        if find_terms(text, [actor.name, *(actor.aliases or [])]):
            found.append(actor)
    return found
