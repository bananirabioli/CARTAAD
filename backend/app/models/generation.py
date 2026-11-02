from datetime import datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

PIECE_STATUSES = ("generado", "bloqueado", "aprobado", "descartado", "programado", "publicado")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("owned_accounts.id", ondelete="SET NULL"), nullable=True)
    format_slug: Mapped[str] = mapped_column(String(80))
    flow: Mapped[str] = mapped_column(String(2))
    strategy: Mapped[str] = mapped_column(String(30))
    variant_styles: Mapped[list[str]] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="generando")  # generando | listo | error
    error: Mapped[str] = mapped_column(Text, default="")
    excluded_creatives: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    learning_context: Mapped[dict[str, Any]] = mapped_column(default=dict)
    options: Mapped[dict[str, Any]] = mapped_column(default=dict)  # MVP: mode, network, image_count, video, instructions
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    pieces: Mapped[list["Piece"]] = relationship(back_populates="proposal", order_by="Piece.id")


class Piece(Base):
    """A reviewable unit: one copy variant or one creative."""

    __tablename__ = "pieces"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # copy | creative | image | video
    creative_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    format_slug: Mapped[str] = mapped_column(String(80))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("owned_accounts.id", ondelete="SET NULL"), nullable=True)
    flow: Mapped[str] = mapped_column(String(2), default="A")
    style_id: Mapped[int | None] = mapped_column(ForeignKey("styles.id", ondelete="SET NULL"), nullable=True)
    style_slug: Mapped[str] = mapped_column(String(80))
    style_version: Mapped[int] = mapped_column(Integer, default=1)
    strategy: Mapped[str] = mapped_column(String(30))
    intensity: Mapped[int] = mapped_column(Integer, default=1)
    effective_tags: Mapped[list[str]] = mapped_column(default=list)
    applied_directives: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    adaptation: Mapped[str | None] = mapped_column(Text, nullable=True)
    why: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    missing_inputs: Mapped[list[str]] = mapped_column(default=list)
    renders: Mapped[list[str]] = mapped_column(default=list)
    render_status: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | listo | error | no_aplica
    render_error: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="generado", index=True)
    validation: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    validation_status: Mapped[str] = mapped_column(String(10), default="ok")
    compliance: Mapped[dict[str, Any]] = mapped_column(default=dict)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_breakdown: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    red_team_summary: Mapped[dict[str, int]] = mapped_column(default=dict)
    legal_required: Mapped[bool] = mapped_column(default=False)
    legal_status: Mapped[str] = mapped_column(String(20), default="no_requerida")
    legal_reason: Mapped[str] = mapped_column(Text, default="")
    legal_note: Mapped[str] = mapped_column(Text, default="")
    legal_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    legal_at: Mapped[datetime | None] = mapped_column(nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    approved_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    discard_reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)

    proposal: Mapped[Proposal] = relationship(back_populates="pieces")
    versions: Mapped[list["PieceVersion"]] = relationship(back_populates="piece", cascade="all, delete-orphan", order_by="PieceVersion.version")
    figures: Mapped[list["FigureCheck"]] = relationship(back_populates="piece", cascade="all, delete-orphan", order_by="FigureCheck.id")
    red_team_notes: Mapped[list["RedTeamNote"]] = relationship(back_populates="piece", cascade="all, delete-orphan", order_by="RedTeamNote.id")


class PieceVersion(Base):
    __tablename__ = "piece_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(default=dict)
    style_slug: Mapped[str] = mapped_column(String(80))
    style_version: Mapped[int] = mapped_column(Integer, default=1)
    strategy: Mapped[str] = mapped_column(String(30))
    intensity: Mapped[int] = mapped_column(Integer, default=1)
    author_type: Mapped[str] = mapped_column(String(10))  # ia | persona
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), default="generar")
    instruction: Mapped[str] = mapped_column(Text, default="")
    diff: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    ai_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    piece: Mapped[Piece] = relationship(back_populates="versions")


class FigureCheck(Base):
    """One extracted figure of the current version; a person must verify each one before approval (HR-09)."""

    __tablename__ = "figure_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    piece_version: Mapped[int] = mapped_column(Integer)
    raw: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(60), nullable=True)
    location: Mapped[str] = mapped_column(String(80), default="")
    fact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched: Mapped[bool] = mapped_column(default=False)
    status: Mapped[str] = mapped_column(String(20), default="pendiente")  # pendiente | verificada | rechazada
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)

    piece: Mapped[Piece] = relationship(back_populates="figures")


class RedTeamNote(Base):
    __tablename__ = "red_team_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    piece_version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # replica | punto_debil
    severity: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text, default="")
    ai_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    piece: Mapped[Piece] = relationship(back_populates="red_team_notes")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))  # aprobar | descartar | editar | verificar_cifra | legal_liberar | legal_bloquear | consentimiento | copiloto
    piece_version: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ConsentRecord(Base):
    """Consent attached to a real testimony (A10 «Voz ciudadana», HR-07)."""

    __tablename__ = "consent_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    person_label: Mapped[str] = mapped_column(String(200))
    testimony: Mapped[str] = mapped_column(Text, default="")
    file_key: Mapped[str] = mapped_column(String(400))
    signed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
