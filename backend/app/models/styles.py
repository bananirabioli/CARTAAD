from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

STYLE_STATUSES = ("borrador", "revision", "activo", "archivado")
DIRECTIVE_TYPES = ("narrativa", "estilo", "linea_roja", "leyenda", "vocabulario", "prioridad_tematica")
DIRECTIVE_STATUSES = ("borrador", "en_revision", "activa", "archivada", "rechazada")
CONFLICT_STATUSES = ("sin_conflicto", "advertencia", "resuelto_por_prioridad", "conflicto_bloqueante", "rechazada_por_regla_dura")


class TagDimension(Base):
    __tablename__ = "tag_dimensions"
    __table_args__ = (UniqueConstraint("client_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="categorical")  # categorical | numeric
    min_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ord: Mapped[int] = mapped_column(Integer, default=0)

    tags: Mapped[list["Tag"]] = relationship(back_populates="dimension", cascade="all, delete-orphan", order_by="Tag.ord")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("dimension_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    dimension_id: Mapped[int] = mapped_column(ForeignKey("tag_dimensions.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    ord: Mapped[int] = mapped_column(Integer, default=0)

    dimension: Mapped[TagDimension] = relationship(back_populates="tags")


class Style(Base):
    """One row per version. Only one `activo` per (client, slug). client_id NULL = base template."""

    __tablename__ = "styles"
    __table_args__ = (UniqueConstraint("client_id", "slug", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="borrador")
    tags: Mapped[dict[str, list[str]]] = mapped_column(default=dict)
    free_tags: Mapped[list[str]] = mapped_column(default=list)
    intensity_min: Mapped[int] = mapped_column(Integer, default=1)
    intensity_max: Mapped[int] = mapped_column(Integer, default=2)
    voice: Mapped[dict[str, Any]] = mapped_column(default=dict)
    guidelines: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {"haz": [...], "evita": [...]}
    preferred_vocab: Mapped[list[str]] = mapped_column(default=list)
    prohibited_vocab: Mapped[list[str]] = mapped_column(default=list)
    length: Mapped[dict[str, Any]] = mapped_column(default=dict)  # {"copy_principal": {"min": 120, "max": 280}}
    emoji_usage: Mapped[str] = mapped_column(String(20), default="ninguno")
    caps_usage: Mapped[str] = mapped_column(String(20), default="normal")
    good_examples: Mapped[list[str]] = mapped_column(default=list)
    bad_examples: Mapped[list[str]] = mapped_column(default=list)
    visual_guide: Mapped[str] = mapped_column(Text, default="")
    palette: Mapped[list[str]] = mapped_column(default=list)
    allowed_formats: Mapped[list[str]] = mapped_column(default=list)
    risk: Mapped[str] = mapped_column(String(10), default="bajo")
    requires_legal: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    legal_approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("styles.id", ondelete="SET NULL"), nullable=True)
    change_note: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class Directive(Base):
    """Governed editorial rule. One row per version (code + version)."""

    __tablename__ = "directives"
    __table_args__ = (UniqueConstraint("client_id", "code", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    dtype: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text, default="")
    structured: Mapped[dict[str, Any]] = mapped_column(default=dict)
    scope: Mapped[dict[str, Any]] = mapped_column(default=dict)  # topics, formats, accounts, styles, flows
    mandatory: Mapped[str] = mapped_column(String(20), default="sugerida")  # obligatoria | sugerida
    priority: Mapped[int] = mapped_column(Integer, default=50)
    valid_from: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="borrador")
    conflict_status: Mapped[str] = mapped_column(String(30), default="sin_conflicto")
    conflict_report: Mapped[dict[str, Any]] = mapped_column(default=dict)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class CreativeType(Base):
    __tablename__ = "creative_types"
    __table_args__ = (UniqueConstraint("client_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(10))
    flow: Mapped[str] = mapped_column(String(2))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    required_slots: Mapped[list[str]] = mapped_column(default=list)
    template: Mapped[str] = mapped_column(String(60))
    requires_fact: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_real_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    text_only: Mapped[bool] = mapped_column(Boolean, default=False)
    is_comparison: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ord: Mapped[int] = mapped_column(Integer, default=0)


class Format(Base):
    __tablename__ = "formats"
    __table_args__ = (UniqueConstraint("client_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    slug: Mapped[str] = mapped_column(String(80))
    code: Mapped[str] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    default_style_slug: Mapped[str] = mapped_column(String(80))
    allowed_style_slugs: Mapped[list[str]] = mapped_column(default=list)
    template: Mapped[str] = mapped_column(String(60))
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    ord: Mapped[int] = mapped_column(Integer, default=0)


class CreativeFormatCompat(Base):
    __tablename__ = "creative_format_compat"
    __table_args__ = (UniqueConstraint("client_id", "creative_slug", "format_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    creative_slug: Mapped[str] = mapped_column(String(80))
    format_slug: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(10))  # full | partial | none
    note: Mapped[str] = mapped_column(Text, default="")
