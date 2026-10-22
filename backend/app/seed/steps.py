"""Ordered seed steps after core (clients + users). Each milestone appends its step."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.core import Client

SeedStep = Callable[[Session, dict[str, Client]], None]

STEPS: list[SeedStep] = []
