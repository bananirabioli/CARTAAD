"""Production seed (DEMO_MODE=false): one client with the base catalogs, the master user and its main account.

No demo data: no facts, sources, posts, cases or topics. Topics start empty and are created from Catálogos.
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal, utcnow
from app.models.core import Client, User, UserClient
from app.models.monitoring import OwnedAccount
from app.services.bootstrap import bootstrap_client
from app.services.client_settings import update_client_settings
from app.services.security import hash_password
from app.textnorm import normalize

logger = logging.getLogger("cartaad.seed")

MAIN_ACCOUNT_FORMAT = "formato_clasico"


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(name)).strip("-")[:80] or "cliente"


def ensure_main_account(db: Session, client: Client, user: User | None = None) -> OwnedAccount:
    """Every client gets one registered, verified own account so generation passes HR-02; its handle is edited later."""
    account = db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == client.id, OwnedAccount.account_type == "propia"))
    if account is None:
        account = OwnedAccount(
            client_id=client.id, network="facebook", handle="@cuenta_principal", display_name=f"{client.name} · cuenta principal", account_type="propia",
            format_slug=MAIN_ACCOUNT_FORMAT, default_style_slug=client.default_style_slug, registered=True, verified=True,
            verified_by_id=user.id if user else None, verified_at=utcnow(), notes="Cuenta principal creada al dar de alta el cliente; edita su handle y red.",
        )
        db.add(account)
        db.flush()
    return account


def seed_production(db: Session) -> None:
    s = get_settings()
    if not (s.admin_email and s.admin_password):
        raise SystemExit("Faltan ADMIN_EMAIL y ADMIN_PASSWORD en .env: son el usuario maestro del modo MVP.")
    user = db.scalar(select(User).where(User.email == s.admin_email.lower()))
    if user is None:
        user = User(email=s.admin_email.lower(), name=s.admin_name, role="owner", kb_owner=True, password_hash=hash_password(s.admin_password), is_demo=False)
        db.add(user)
        db.flush()
    client = Client(
        name=s.initial_client_name, slug=slugify(s.initial_client_name), client_type="candidatura",
        default_tone="Cercano y propositivo; datos con fuente; sin ataques personales.", default_style_slug="cercano", restrictions="",
    )
    db.add(client)
    db.flush()
    update_client_settings(client, {"context": s.initial_client_context})
    bootstrap_client(db, client)
    db.add(UserClient(user_id=user.id, client_id=client.id))
    ensure_main_account(db, client, user)
    db.commit()


def seed_production_if_empty() -> bool:
    with SessionLocal() as db:
        if db.scalar(select(Client.id).limit(1)) is not None:
            return False
        logger.info("seeding production client and master user")
        seed_production(db)
        return True
