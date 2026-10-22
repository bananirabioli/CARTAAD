"""Modo veda (HR-04). The model is introduced in M6; until then no restriction is ever active."""

from typing import Any

from sqlalchemy.orm import Session


def active_restriction(db: Session, client_id: int) -> Any | None:
    return None
