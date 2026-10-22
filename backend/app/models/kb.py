from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base, Vector, utcnow

EMBED_DIM = get_settings().embedding_dim


class GovLevel(Base):
    __tablename__ = "gov_levels"
    __table_args__ = (UniqueConstraint("client_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    ord: Mapped[int] = mapped_column(Integer, default=0)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(40), default="informe")
    issuer: Mapped[str] = mapped_column(String(200), default="")
    issued_at: Mapped[datetime | None] = mapped_column(nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    gov_level_id: Mapped[int | None] = mapped_column(ForeignKey("gov_levels.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="procesado")  # pendiente | procesado | error
    error: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan", order_by="DocumentChunk.ord")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    ord: Mapped[int] = mapped_column(Integer)
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)

    document: Mapped[SourceDocument] = relationship(back_populates="chunks")


class Fact(Base):
    __tablename__ = "facts"
    __table_args__ = (UniqueConstraint("client_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(20))
    statement: Mapped[str] = mapped_column(Text)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(60), default="")
    base: Mapped[str] = mapped_column(String(120), default="total")
    period_label: Mapped[str] = mapped_column(String(120), default="")
    period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    fact_date: Mapped[datetime | None] = mapped_column(nullable=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True)
    gov_level_id: Mapped[int | None] = mapped_column(ForeignKey("gov_levels.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    document: Mapped[SourceDocument | None] = relationship()
    gov_level: Mapped[GovLevel | None] = relationship()


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    body_md: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class KeyMessage(Base):
    __tablename__ = "key_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    tone_note: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Competence(Base):
    __tablename__ = "competences"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    gov_level_id: Mapped[int] = mapped_column(ForeignKey("gov_levels.id", ondelete="CASCADE"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    description: Mapped[str] = mapped_column(Text)
    legal_basis: Mapped[str] = mapped_column(Text, default="")

    gov_level: Mapped[GovLevel] = relationship()


class ApprovedImage(Base):
    __tablename__ = "approved_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    file_key: Mapped[str] = mapped_column(String(400))
    credit: Mapped[str] = mapped_column(String(300), default="")
    license: Mapped[str] = mapped_column(String(200), default="")
    taken_at: Mapped[datetime | None] = mapped_column(nullable=True)
    tags: Mapped[list[str]] = mapped_column(default=list)
    image_type: Mapped[str] = mapped_column(String(20), default="foto_real")  # foto_real | ilustracion
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Actor(Base):
    __tablename__ = "actors"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list[str]] = mapped_column(default=list)
    actor_type: Mapped[str] = mapped_column(String(40), default="otro")
    gov_level_id: Mapped[int | None] = mapped_column(ForeignKey("gov_levels.id", ondelete="SET NULL"), nullable=True)
    is_own: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class ResponseHistory(Base):
    __tablename__ = "response_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    piece_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic_slug: Mapped[str] = mapped_column(String(80), index=True)
    format_slug: Mapped[str] = mapped_column(String(80), default="")
    style_slug: Mapped[str] = mapped_column(String(80), default="")
    strategy: Mapped[str] = mapped_column(String(40), default="")
    creative_slug: Mapped[str] = mapped_column(String(80), default="")
    flow: Mapped[str] = mapped_column(String(2), default="A")
    outcome: Mapped[str] = mapped_column(String(20))  # funciono | no_funciono
    reach_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentiment_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    rated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
