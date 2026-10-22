"""Cloners for base catalogs. Imported lazily by bootstrap_client()."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Client, Topic
from app.models.kb import GovLevel
from app.services.bootstrap import register_cloner

DEFAULT_TOPICS = [
    ("baches", "Baches", ["bache", "baches", "pavimento", "calle", "vialidad", "hoyo", "asfalto", "repavimentación"]),
    ("seguridad", "Seguridad", ["seguridad", "robo", "asalto", "patrulla", "policía", "delito", "vigilancia", "luminarias"]),
    ("agua", "Agua", ["agua", "pipa", "tandeo", "fuga", "drenaje", "presión", "garrafón", "abasto"]),
    ("obra_publica", "Obra pública", ["obra", "construcción", "puente", "parque", "inauguración", "licitación", "remodelación"]),
]


@register_cloner("topics")
def clone_topics(db: Session, client: Client) -> None:
    existing = set(db.scalars(select(Topic.slug).where(Topic.client_id == client.id)))
    for slug, name, keywords in DEFAULT_TOPICS:
        if slug not in existing:
            db.add(Topic(client_id=client.id, slug=slug, name=name, keywords=keywords))


DEFAULT_GOV_LEVELS = [("municipio", "Municipio", 1), ("estado", "Estado", 2), ("federacion", "Federación", 3)]


@register_cloner("gov_levels")
def clone_gov_levels(db: Session, client: Client) -> None:
    existing = set(db.scalars(select(GovLevel.slug).where(GovLevel.client_id == client.id)))
    for slug, name, ord_ in DEFAULT_GOV_LEVELS:
        if slug not in existing:
            db.add(GovLevel(client_id=client.id, slug=slug, name=name, ord=ord_))
