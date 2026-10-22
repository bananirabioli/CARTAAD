from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class ScheduledPost(Base):
    """One approved piece on one registered account at one time (simulated publishing; no bulk publishing exists)."""

    __tablename__ = "scheduled_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    copy_piece_id: Mapped[int | None] = mapped_column(ForeignKey("pieces.id", ondelete="SET NULL"), nullable=True)
    piece_version: Mapped[int] = mapped_column(default=1)
    account_id: Mapped[int] = mapped_column(ForeignKey("owned_accounts.id", ondelete="CASCADE"))
    scheduled_at: Mapped[datetime] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="programado")  # programado | publicado | cancelado | error
    text: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AllyPackage(Base):
    __tablename__ = "ally_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text, default="")
    suggested_copy: Mapped[str] = mapped_column(Text, default="")
    piece_ids: Mapped[list[int]] = mapped_column(default=list)
    expires_at: Mapped[datetime]
    revoked: Mapped[bool] = mapped_column(default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class AllyShare(Base):
    __tablename__ = "ally_shares"

    id: Mapped[int] = mapped_column(primary_key=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("ally_packages.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("owned_accounts.id", ondelete="CASCADE"))
    piece_id: Mapped[int | None] = mapped_column(ForeignKey("pieces.id", ondelete="SET NULL"), nullable=True)
    shared_by_name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
