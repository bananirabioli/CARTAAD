from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base, Vector, utcnow

NETWORKS = ("facebook", "instagram", "x", "tiktok", "otra")
SOURCE_TYPES = ("medio", "influencer", "pagina_ciudadana", "actor_politico")
PRIORITIES = ("alta", "media", "baja")


class MonitoredSource(Base):
    __tablename__ = "monitored_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    network: Mapped[str] = mapped_column(String(20))
    handle: Mapped[str] = mapped_column(String(120), default="")
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_type: Mapped[str] = mapped_column(String(30))
    priority: Mapped[str] = mapped_column(String(10), default="media")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    check_frequency_minutes: Mapped[int] = mapped_column(Integer, default=60)
    adapter: Mapped[str] = mapped_column(String(30), default="mock")  # mock | file | social_listening
    baseline_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_since: Mapped[datetime | None] = mapped_column(nullable=True)
    baseline_computed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class OwnedAccount(Base):
    """Own, allied or spokesperson account registered and verified by the team (HR-02)."""

    __tablename__ = "owned_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    network: Mapped[str] = mapped_column(String(20))
    handle: Mapped[str] = mapped_column(String(120))
    display_name: Mapped[str] = mapped_column(String(200))
    account_type: Mapped[str] = mapped_column(String(20))  # propia | aliada | voceria
    format_slug: Mapped[str] = mapped_column(String(80))
    default_style_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    registered: Mapped[bool] = mapped_column(Boolean, default=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (UniqueConstraint("client_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("monitored_sources.id", ondelete="SET NULL"), nullable=True, index=True)
    origin: Mapped[str] = mapped_column(String(20), default="automatica")  # automatica | manual
    network: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text, default="")
    image_key: Mapped[str | None] = mapped_column(String(400), nullable=True)
    image_text: Mapped[str] = mapped_column(Text, default="")
    visual_context: Mapped[str] = mapped_column(Text, default="")
    names_blurred: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    published_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    captured_at: Mapped[datetime] = mapped_column(default=utcnow)
    captured_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_history: Mapped[bool] = mapped_column(Boolean, default=False)  # only used to build baselines
    embedding: Mapped[list[float] | None] = mapped_column(Vector(get_settings().embedding_dim), nullable=True)
    # Alert cache (recomputed on every snapshot)
    velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    alert_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # bajo|medio|alto|critico|sin_linea_base
    total_interactions: Mapped[int] = mapped_column(Integer, default=0)
    alert_computed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(default=dict)

    source: Mapped[MonitoredSource | None] = relationship()
    snapshots: Mapped[list["InteractionSnapshot"]] = relationship(back_populates="post", cascade="all, delete-orphan", order_by="InteractionSnapshot.taken_at")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class InteractionSnapshot(Base):
    __tablename__ = "interaction_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    taken_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped[Post] = relationship(back_populates="snapshots")

    @property
    def total(self) -> int:
        return self.likes + self.comments + self.shares


class Comment(Base):
    """Aggregated text only. No author name, handle or id is ever stored (HR-03)."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    stance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    theme: Mapped[str | None] = mapped_column(String(80), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(default=utcnow)

    post: Mapped[Post] = relationship(back_populates="comments")
