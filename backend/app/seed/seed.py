"""Demo seed data. Everything is fictitious: municipality, actors, parties, people and media."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.core import Client, User, UserClient
from app.services.bootstrap import bootstrap_client
from app.services.security import hash_password

logger = logging.getLogger("cartaad.seed")

DEMO_PASSWORD = "demo1234"

CLIENTS = [
    {
        "slug": "municipio-ejemplo",
        "name": "Municipio Ejemplo",
        "client_type": "gobierno",
        "default_tone": "Institucional y cercano; datos con fuente; sin adjetivos sobre adversarios.",
        "default_style_slug": "institucional",
        "restrictions": "Comunicación gubernamental: sin propaganda personalizada; respetar periodos de veda.",
    },
    {
        "slug": "candidatura-ejemplo",
        "name": "Candidatura Ciudadana Ejemplo",
        "client_type": "candidatura",
        "default_tone": "Cercano y propositivo; contraste con datos, nunca ataques personales.",
        "default_style_slug": "cercano",
        "restrictions": "Campaña: toda pieza pasa por verificación de cifras y, si es satírica, por legal.",
    },
]

USERS = [
    ("analista@demo.mx", "Ana Analista", "analista", False, None),
    ("aprobador@demo.mx", "Pablo Aprobador", "aprobador", False, None),
    ("legal@demo.mx", "Lucía Legal", "legal", False, None),
    ("diseno@demo.mx", "Diego Diseño", "diseno", False, None),
    ("admin@demo.mx", "Ada Admin", "admin", False, None),
    ("base@demo.mx", "Karla Base (dueña de la base)", "analista", True, None),
    ("candidatura@demo.mx", "Carla Campaña", "analista", False, "candidatura-ejemplo"),
]


def seed_core(db: Session) -> dict[str, Client]:
    clients: dict[str, Client] = {}
    for data in CLIENTS:
        client = db.scalar(select(Client).where(Client.slug == data["slug"]))
        if client is None:
            client = Client(**data)
            db.add(client)
            db.flush()
        bootstrap_client(db, client)
        clients[data["slug"]] = client
    pwd = hash_password(DEMO_PASSWORD)
    for email, name, role, kb_owner, only_client in USERS:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=name, role=role, kb_owner=kb_owner, password_hash=pwd, is_demo=only_client is None)
            db.add(user)
            db.flush()
        targets = [clients[only_client]] if only_client else list(clients.values())
        for client in targets:
            if not db.scalar(select(UserClient).where(UserClient.user_id == user.id, UserClient.client_id == client.id)):
                db.add(UserClient(user_id=user.id, client_id=client.id))
    db.flush()
    return clients


def run_seed(db: Session) -> None:
    from app.seed import steps

    clients = seed_core(db)
    for step in steps.STEPS:
        step(db, clients)
    db.commit()


def seed_if_empty() -> bool:
    with SessionLocal() as db:
        if db.scalar(select(Client.id).limit(1)) is not None:
            return False
        logger.info("seeding demo data")
        run_seed(db)
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        run_seed(session)
    print("seed ok")
