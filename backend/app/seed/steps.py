"""Ordered seed steps after core (clients + users). Each milestone appends its step."""

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models.core import Client
from app.seed.advanced_seed import seed_advanced_cases
from app.seed.cases_seed import seed_cases
from app.seed.kb_seed import seed_kb
from app.seed.monitoring_seed import seed_monitoring
from app.seed.styles_seed import seed_styles

SeedStep = Callable[[Session, dict[str, Client]], None]

STEPS: list[SeedStep] = [seed_kb, seed_styles, seed_monitoring, seed_cases, seed_advanced_cases]
