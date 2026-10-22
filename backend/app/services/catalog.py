"""Catalog lookups: formats, creatives, creative × format matrix and effective style selection."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.i18n import t
from app.models.core import Client
from app.models.styles import CreativeFormatCompat, CreativeType, Format, Style


def formats(db: Session, client_id: int, active_only: bool = True) -> list[Format]:
    stmt = select(Format).where(Format.client_id == client_id)
    if active_only:
        stmt = stmt.where(Format.active.is_(True))
    return list(db.scalars(stmt.order_by(Format.ord)))


def get_format(db: Session, client_id: int, slug: str | None) -> Format | None:
    if not slug:
        return None
    return db.scalar(select(Format).where(Format.client_id == client_id, Format.slug == slug))


def creatives(db: Session, client_id: int, flow: str | None = None, active_only: bool = True) -> list[CreativeType]:
    stmt = select(CreativeType).where(CreativeType.client_id == client_id)
    if flow:
        stmt = stmt.where(CreativeType.flow == flow)
    if active_only:
        stmt = stmt.where(CreativeType.active.is_(True))
    return list(db.scalars(stmt.order_by(CreativeType.ord)))


def get_creative(db: Session, client_id: int, slug: str) -> CreativeType | None:
    return db.scalar(select(CreativeType).where(CreativeType.client_id == client_id, CreativeType.slug == slug))


def compat(db: Session, client_id: int, creative_slug: str, format_slug: str) -> tuple[str, str]:
    row = db.scalar(
        select(CreativeFormatCompat).where(
            CreativeFormatCompat.client_id == client_id, CreativeFormatCompat.creative_slug == creative_slug, CreativeFormatCompat.format_slug == format_slug
        )
    )
    return (row.level, row.note) if row else ("none", t("validators.compat.not_in_matrix"))


def matrix(db: Session, client_id: int) -> dict[tuple[str, str], CreativeFormatCompat]:
    rows = db.scalars(select(CreativeFormatCompat).where(CreativeFormatCompat.client_id == client_id))
    return {(r.creative_slug, r.format_slug): r for r in rows}


def active_style(db: Session, client_id: int, slug: str | None) -> Style | None:
    if not slug:
        return None
    return db.scalar(select(Style).where(Style.client_id == client_id, Style.slug == slug, Style.status == "activo"))


def active_styles(db: Session, client_id: int) -> list[Style]:
    return list(db.scalars(select(Style).where(Style.client_id == client_id, Style.status == "activo").order_by(Style.name)))


def format_style_slugs(fmt: Format) -> list[str]:
    slugs = [fmt.default_style_slug, *[s for s in fmt.allowed_style_slugs or [] if s != fmt.default_style_slug]]
    return [s for s in slugs if s]


def style_allowed_for_format(style: Style, fmt: Format) -> bool:
    in_format = style.slug in format_style_slugs(fmt)
    in_style = not style.allowed_formats or fmt.slug in style.allowed_formats
    return in_format and in_style


@dataclass
class StyleChoice:
    slug: str | None
    source: str  # persona | cuenta | formato | cliente
    reason: str


def effective_style(client: Client, fmt: Format | None, account_default: str | None, chosen: str | None) -> StyleChoice:
    """Precedence (7.3): chosen by the person > account default > format default > client default."""
    if chosen:
        return StyleChoice(chosen, "persona", t("styles.choice.persona", style=chosen))
    if account_default:
        return StyleChoice(account_default, "cuenta", t("styles.choice.cuenta", style=account_default))
    if fmt and fmt.default_style_slug:
        return StyleChoice(fmt.default_style_slug, "formato", t("styles.choice.formato", style=fmt.default_style_slug, format=fmt.name))
    return StyleChoice(client.default_style_slug, "cliente", t("styles.choice.cliente", style=client.default_style_slug or ""))
