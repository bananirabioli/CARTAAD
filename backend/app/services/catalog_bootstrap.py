"""Cloners for base catalogs. Imported lazily by bootstrap_client()."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.core import Client, Topic
from app.models.kb import GovLevel
from app.services.bootstrap import register_cloner

# Keywords prefixed with "~" are weak signals (count half) for topic detection.
DEFAULT_TOPICS = [
    ("baches", "Baches", ["bache", "bacheo", "pavimento", "repavimenta", "~calle", "vialidad", "vial", "hoyo", "asfalto"]),
    ("seguridad", "Seguridad", ["seguridad", "inseguridad", "robo a", "asalto", "patrulla", "policía", "policial", "delito", "delincuente", "fiscalía", "vigilancia", "luminaria"]),
    ("agua", "Agua", ["agua", "pipa", "tandeo", "fuga", "drenaje", "presión", "garrafón", "abasto", "acueducto", "tubería"]),
    ("obra_publica", "Obra pública", ["obra", "construcción", "puente", "parque", "inauguración", "licitación", "remodelación", "rehabilit", "banqueta", "etapa"]),
]


@register_cloner("topics")
def clone_topics(db: Session, client: Client) -> None:
    if not get_settings().demo_mode:
        return  # MVP: every client builds its own topics from scratch
    existing = set(db.scalars(select(Topic.slug).where(Topic.client_id == client.id)))
    for slug, name, keywords in DEFAULT_TOPICS:
        if slug not in existing:
            db.add(Topic(client_id=client.id, slug=slug, name=name, keywords=keywords))


DEFAULT_GOV_LEVELS = [("municipio", "Municipio", 1), ("estado", "Estado", 2), ("federacion", "Federación", 3)]


@register_cloner("gov_levels")
def clone_gov_levels(db: Session, client: Client) -> None:
    if not get_settings().demo_mode:
        return
    existing = set(db.scalars(select(GovLevel.slug).where(GovLevel.client_id == client.id)))
    for slug, name, ord_ in DEFAULT_GOV_LEVELS:
        if slug not in existing:
            db.add(GovLevel(client_id=client.id, slug=slug, name=name, ord=ord_))


# ------------------------------------------------------------------ base templates (client_id = NULL)


def ensure_base_templates(db: Session) -> None:
    from app.models.styles import CreativeFormatCompat, CreativeType, Format, Style, Tag, TagDimension
    from app.seed import catalog_data as cd

    if db.scalar(select(TagDimension.id).where(TagDimension.client_id.is_(None)).limit(1)) is None:
        for i, (slug, name, kind, values) in enumerate(cd.TAG_DIMENSIONS):
            dim = TagDimension(client_id=None, slug=slug, name=name, kind=kind, ord=i, min_value=1 if kind == "numeric" else None, max_value=5 if kind == "numeric" else None)
            db.add(dim)
            db.flush()
            for j, value in enumerate(values):
                db.add(Tag(dimension_id=dim.id, client_id=None, slug=value, name=cd.TAG_LABELS.get(value, value.replace("_", " ")), ord=j))
    if db.scalar(select(Style.id).where(Style.client_id.is_(None)).limit(1)) is None:
        for spec in cd.STYLES:
            db.add(Style(client_id=None, status="activo", version=1, **spec))
    if db.scalar(select(Format.id).where(Format.client_id.is_(None)).limit(1)) is None:
        for i, spec in enumerate(cd.FORMATS):
            db.add(Format(client_id=None, ord=i, **spec))
    if db.scalar(select(CreativeType.id).where(CreativeType.client_id.is_(None)).limit(1)) is None:
        for i, row in enumerate(cd.CREATIVES):
            slug, code, flow, name, desc, slots, template, req_fact, req_consent, req_photo, text_only, is_cmp = row
            db.add(
                CreativeType(
                    client_id=None, slug=slug, code=code, flow=flow, name=name, description=desc, required_slots=slots, template=template,
                    requires_fact=req_fact, requires_consent=req_consent, requires_real_photo=req_photo, text_only=text_only, is_comparison=is_cmp, ord=i,
                )
            )
    if db.scalar(select(CreativeFormatCompat.id).where(CreativeFormatCompat.client_id.is_(None)).limit(1)) is None:
        for creative, fmt, level, note in cd.matrix_rows():
            db.add(CreativeFormatCompat(client_id=None, creative_slug=creative, format_slug=fmt, level=level, note=note))
    db.flush()


_COPY_SKIP = {"id", "client_id", "created_at", "updated_at"}


def _clone(obj, **overrides):  # noqa: ANN001, ANN003, ANN202
    from sqlalchemy import inspect as sa_inspect

    data = {c.key: getattr(obj, c.key) for c in sa_inspect(obj).mapper.column_attrs if c.key not in _COPY_SKIP}
    data.update(overrides)
    return type(obj)(**data)


@register_cloner("tags")
def clone_tags(db: Session, client: Client) -> None:
    from app.models.styles import Tag, TagDimension

    ensure_base_templates(db)
    if db.scalar(select(TagDimension.id).where(TagDimension.client_id == client.id).limit(1)):
        return
    for dim in db.scalars(select(TagDimension).where(TagDimension.client_id.is_(None)).order_by(TagDimension.ord)):
        new_dim = _clone(dim, client_id=client.id)
        db.add(new_dim)
        db.flush()
        for tag in dim.tags:
            db.add(_clone(tag, client_id=client.id, dimension_id=new_dim.id))


@register_cloner("styles")
def clone_styles(db: Session, client: Client) -> None:
    from app.models.styles import Style

    ensure_base_templates(db)
    existing = set(db.scalars(select(Style.slug).where(Style.client_id == client.id)))
    for base in db.scalars(select(Style).where(Style.client_id.is_(None), Style.status == "activo")):
        if base.slug not in existing:
            db.add(_clone(base, client_id=client.id, parent_id=base.id, status="activo", version=1, change_note="Clonado de la plantilla base"))


@register_cloner("catalogs")
def clone_catalogs(db: Session, client: Client) -> None:
    from app.models.styles import CreativeFormatCompat, CreativeType, Format

    ensure_base_templates(db)
    for model in (Format, CreativeType, CreativeFormatCompat):
        if db.scalar(select(model.id).where(model.client_id == client.id).limit(1)):
            continue
        for base in db.scalars(select(model).where(model.client_id.is_(None))):
            db.add(_clone(base, client_id=client.id))
