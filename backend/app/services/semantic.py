"""Nearest-neighbour search over embedding columns: pgvector on PostgreSQL, Python cosine elsewhere."""

from typing import Any, TypeVar

from sqlalchemy import Float, bindparam, select
from sqlalchemy.orm import Session

from app.ai.embeddings import cosine, embed
from app.db import Vector

M = TypeVar("M")


def nearest(db: Session, model: type[M], query_vec: list[float], *filters: Any, limit: int = 10, min_score: float = 0.0) -> list[tuple[M, float]]:
    column = model.embedding  # type: ignore[attr-defined]
    base = select(model).where(column.is_not(None), *filters)
    if db.get_bind().dialect.name == "postgresql":
        qp = bindparam("qvec", value=query_vec, type_=Vector(len(query_vec)))
        dist = column.op("<=>", return_type=Float)(qp)
        rows = db.execute(base.add_columns(dist.label("dist")).order_by(dist).limit(limit)).all()
        scored = [(row[0], 1.0 - float(row[1])) for row in rows]
    else:
        scored = [(obj, cosine(query_vec, obj.embedding)) for obj in db.scalars(base)]  # type: ignore[attr-defined]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        scored = scored[:limit]
    return [(obj, score) for obj, score in scored if score >= min_score]


def search_text(db: Session, model: type[M], text: str, *filters: Any, limit: int = 10, min_score: float = 0.0) -> list[tuple[M, float]]:
    return nearest(db, model, embed(text), *filters, limit=limit, min_score=min_score)
