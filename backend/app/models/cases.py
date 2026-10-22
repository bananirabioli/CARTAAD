from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

CASE_STATUSES = (
    "capturado", "clasificado", "interpretado", "revision_legal", "listo_para_generar", "generando", "generado", "en_revision",
    "aprobado", "programado", "publicado", "medido", "calificado", "monitoreando", "ignorado", "canalizado", "descartado",
)
TERMINAL_STATUSES = ("monitoreando", "ignorado", "canalizado", "descartado", "calificado")


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    stance: Mapped[str] = mapped_column(String(20))
    topic_slug: Mapped[str] = mapped_column(String(80))
    message_type: Mapped[str] = mapped_column(String(40))
    alert_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alert_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    canalizar_a_atencion: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    edited_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), unique=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(30), default="capturado", index=True)
    flow: Mapped[str | None] = mapped_column(String(2), nullable=True)
    topic_slug: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    message_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    alert_level: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(nullable=True)
    strategy_suggested: Mapped[str | None] = mapped_column(String(30), nullable=True)
    strategy_justification: Mapped[str] = mapped_column(Text, default="")
    strategy_alternatives: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    strategy: Mapped[str | None] = mapped_column(String(30), nullable=True)
    style_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    style_choice: Mapped[dict[str, Any]] = mapped_column(default=dict)
    recommended_style: Mapped[dict[str, Any]] = mapped_column(default=dict)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("owned_accounts.id", ondelete="SET NULL"), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_breakdown: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    legal_required: Mapped[bool] = mapped_column(Boolean, default=False)
    legal_status: Mapped[str] = mapped_column(String(20), default="no_requerida")  # no_requerida | pendiente | liberada | bloqueada
    legal_note: Mapped[str] = mapped_column(Text, default="")
    legal_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    legal_at: Mapped[datetime | None] = mapped_column(nullable=True)
    canalizar_a_atencion: Mapped[bool] = mapped_column(Boolean, default=False)
    learning_context: Mapped[dict[str, Any]] = mapped_column(default=dict)
    closed_reason: Mapped[str] = mapped_column(Text, default="")
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rating_note: Mapped[str] = mapped_column(Text, default="")
    rated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)

    interpretation: Mapped["Interpretation | None"] = relationship(back_populates="case", cascade="all, delete-orphan", uselist=False)


class Interpretation(Base):
    __tablename__ = "interpretations"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), unique=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    narrative: Mapped[str] = mapped_column(Text, default="")
    missing_context: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    comments_summary: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    repeated_in: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    fact_ids_considered: Mapped[list[int]] = mapped_column(default=list)
    ai_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    case: Mapped[Case] = relationship(back_populates="interpretation")
    claims: Mapped[list["Claim"]] = relationship(back_populates="interpretation", cascade="all, delete-orphan", order_by="Claim.id")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    interpretation_id: Mapped[int] = mapped_column(ForeignKey("interpretations.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    verdict: Mapped[str] = mapped_column(String(20))
    fact_ids: Mapped[list[int]] = mapped_column(default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    missing_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    interpretation: Mapped[Interpretation] = relationship(back_populates="claims")
