from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

CLIENT_TYPES = ("gobierno", "partido", "candidatura")
ROLES = ("analista", "aprobador", "legal", "diseno", "admin")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    client_type: Mapped[str] = mapped_column(String(20))
    default_tone: Mapped[str] = mapped_column(Text, default="")
    default_style_slug: Mapped[str | None] = mapped_column(String(80), nullable=True)
    restrictions: Mapped[str] = mapped_column(Text, default="")
    settings: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20))
    kb_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    clients: Mapped[list["UserClient"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserClient(Base):
    __tablename__ = "user_clients"
    __table_args__ = (UniqueConstraint("user_id", "client_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"))

    user: Mapped[User] = relationship(back_populates="clients")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("client_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[list[str]] = mapped_column(default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_label: Mapped[str] = mapped_column(String(200), default="sistema")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


class Sequence(Base):
    """Per-client human-readable codes (C-0001, H-001, D-001...)."""

    __tablename__ = "sequences"
    __table_args__ = (UniqueConstraint("client_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(40))
    value: Mapped[int] = mapped_column(Integer, default=0)
