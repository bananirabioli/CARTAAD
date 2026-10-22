"""Fact helpers: validity, visible source label (HR-01), serialization and CSV import."""

import csv
import io
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import embed
from app.db import utcnow
from app.guardrails.hard_rules import source_label
from app.models.core import Topic, User
from app.models.kb import Fact, GovLevel, SourceDocument
from app.schemas.kb import FactOut


def is_expired(fact: Fact, now: datetime | None = None) -> bool:
    return bool(fact.valid_until and fact.valid_until < (now or utcnow()))


def fact_label(fact: Fact) -> str:
    doc = fact.document
    return source_label(fact, doc.title if doc else None, (doc.issued_at if doc else None) or fact.fact_date)


def fact_text_for_embedding(fact: Fact) -> str:
    return f"{fact.statement} {fact.unit} {fact.period_label} {fact.notes}"


def refresh_embedding(fact: Fact) -> None:
    fact.embedding = embed(fact_text_for_embedding(fact))


def fact_out(db: Session, fact: Fact) -> FactOut:
    out = FactOut.model_validate(fact)
    topic = db.get(Topic, fact.topic_id) if fact.topic_id else None
    verifier = db.get(User, fact.verified_by_id) if fact.verified_by_id else None
    return out.model_copy(
        update={
            "gov_level_name": fact.gov_level.name if fact.gov_level else None,
            "topic_slug": topic.slug if topic else None,
            "verified_by_name": verifier.name if verifier else None,
            "expired": is_expired(fact),
            "source_label": f"{fact.code} · {fact_label(fact)}",
        }
    )


def facts_by_ids(db: Session, client_id: int, ids: list[int]) -> dict[int, Fact]:
    if not ids:
        return {}
    return {f.id: f for f in db.scalars(select(Fact).where(Fact.client_id == client_id, Fact.id.in_(ids)))}


def _date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.fromisoformat(value)


def import_facts_csv(db: Session, client_id: int, data: bytes, next_code) -> dict[str, Any]:  # noqa: ANN001
    """Columns: code?, statement, value, unit, base, period_label, period_start, period_end, fact_date,
    document (title or id), gov_level (slug), topic (slug), valid_until, notes."""
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    levels = {g.slug: g.id for g in db.scalars(select(GovLevel).where(GovLevel.client_id == client_id))}
    topics = {t.slug: t.id for t in db.scalars(select(Topic).where(Topic.client_id == client_id))}
    docs = list(db.scalars(select(SourceDocument).where(SourceDocument.client_id == client_id)))
    by_title = {d.title.strip().lower(): d.id for d in docs}
    by_id = {str(d.id): d.id for d in docs}
    created = updated = 0
    errors: list[dict[str, Any]] = []
    for line_no, row in enumerate(reader, start=2):
        try:
            statement = (row.get("statement") or "").strip()
            if len(statement) < 5:
                raise ValueError("statement vacío")
            raw_value = (row.get("value") or "").strip().replace(",", "")
            doc_ref = (row.get("document") or "").strip()
            doc_id = by_id.get(doc_ref) or by_title.get(doc_ref.lower()) if doc_ref else None
            if doc_ref and not doc_id:
                raise ValueError(f"documento no encontrado: {doc_ref}")
            level = (row.get("gov_level") or "").strip()
            topic = (row.get("topic") or "").strip()
            if level and level not in levels:
                raise ValueError(f"nivel no encontrado: {level}")
            if topic and topic not in topics:
                raise ValueError(f"tema no encontrado: {topic}")
            fields = {
                "statement": statement,
                "value": float(raw_value) if raw_value else None,
                "unit": (row.get("unit") or "").strip(),
                "base": (row.get("base") or "total").strip() or "total",
                "period_label": (row.get("period_label") or "").strip(),
                "period_start": _date(row.get("period_start", "")),
                "period_end": _date(row.get("period_end", "")),
                "fact_date": _date(row.get("fact_date", "")),
                "document_id": doc_id,
                "gov_level_id": levels.get(level),
                "topic_id": topics.get(topic),
                "valid_until": _date(row.get("valid_until", "")),
                "notes": (row.get("notes") or "").strip(),
            }
            code = (row.get("code") or "").strip()
            existing = db.scalar(select(Fact).where(Fact.client_id == client_id, Fact.code == code)) if code else None
            if existing:
                for k, v in fields.items():
                    setattr(existing, k, v)
                existing.verified_by_id = None
                existing.verified_at = None
                refresh_embedding(existing)
                updated += 1
            else:
                fact = Fact(client_id=client_id, code=code or next_code(), **fields)
                refresh_embedding(fact)
                db.add(fact)
                created += 1
            db.flush()
        except (ValueError, KeyError) as exc:
            errors.append({"line": line_no, "error": str(exc)})
    return {"created": created, "updated": updated, "errors": errors}
