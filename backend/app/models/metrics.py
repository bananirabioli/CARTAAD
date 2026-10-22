from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, utcnow


class PostMetrics(Base):
    """Results of a published piece. `piece_id` is the variant id used for A/B comparisons."""

    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    piece_id: Mapped[int] = mapped_column(ForeignKey("pieces.id", ondelete="CASCADE"), index=True)
    scheduled_post_id: Mapped[int | None] = mapped_column(ForeignKey("scheduled_posts.id", ondelete="SET NULL"), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(default=utcnow)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    sentiment_pos: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_neg: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_neu: Mapped[float] = mapped_column(Float, default=0.0)
    original_reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    original_sentiment_neg: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | simulado
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
