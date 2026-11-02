"""Builds the context dict shared by generate_copy / refine_piece across providers."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Client, Topic
from app.models.kb import Fact, KeyMessage
from app.services.facts import fact_label, is_expired
from app.services.semantic import search_text
from app.services.style_resolver import ResolvedStyle
from app.textnorm import normalize


def fact_dict(fact: Fact) -> dict[str, Any]:
    doc = fact.document
    when = (doc.issued_at if doc else None) or fact.fact_date
    return {
        "id": fact.id,
        "code": fact.code,
        "statement": fact.statement,
        "value": fact.value,
        "unit": fact.unit,
        "base": fact.base,
        "period_label": fact.period_label,
        "issuer": doc.issuer if doc else "fuente sin documento",
        "document": doc.title if doc else None,
        "date": when.date().isoformat() if when else None,
        "expired": is_expired(fact),
        "has_document": doc is not None,
        "source_label": f"{fact.code} · {fact_label(fact)}",
    }


def detect_topic(db: Session, client_id: int, text: str) -> Topic | None:
    topics = list(db.scalars(select(Topic).where(Topic.client_id == client_id, Topic.active.is_(True))))
    norm = f" {normalize(text)} "
    scored = [(sum(0.5 if kw.startswith("~") else 1.0 for kw in t.keywords or [] if f" {normalize(kw.lstrip('~'))}" in norm), t) for t in topics]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else None


def relevant_facts(db: Session, client_id: int, text: str, topic_id: int | None = None, limit: int = 6, usable_only: bool = True) -> list[Fact]:
    """Facts for a text: same topic first, ranked by semantic similarity; expired / undocumented last (or excluded)."""
    filters = [Fact.client_id == client_id, Fact.status == "activo"]
    hits = search_text(db, Fact, text, *filters, limit=40)
    ranked = sorted(hits, key=lambda pair: (pair[0].topic_id != topic_id if topic_id else False, -pair[1]))
    out = []
    for fact, _score in ranked:
        if usable_only and (is_expired(fact) or fact.document_id is None):
            continue
        out.append(fact)
        if len(out) >= limit:
            break
    return out


def key_messages(db: Session, client_id: int, topic_id: int | None) -> list[str]:
    rows = db.scalars(select(KeyMessage).where(KeyMessage.client_id == client_id, KeyMessage.active.is_(True)).order_by(KeyMessage.priority.desc()))
    return [k.text for k in rows if k.topic_id in (None, topic_id)][:3]


def build_copy_context(
    *,
    client: Client,
    resolved: ResolvedStyle,
    strategy: str,
    flow: str,
    topic: Topic | None,
    post_text: str,
    facts: list[Fact],
    key_msgs: list[str],
    claims: list[dict[str, Any]] | None = None,
    complaint: bool = False,
    format_name: str | None = None,
    closing_phrase: str | None = None,
    account_handle: str | None = None,
    variant: int = 0,
    learning: dict[str, Any] | None = None,
    max_facts: int = 2,
) -> dict[str, Any]:
    s = resolved.style
    return {
        "client_name": client.name,
        "style_block": resolved.style_block(),
        "style": {
            "id": s.id, "slug": s.slug, "name": s.name, "version": s.version, "tags": s.tags, "intensity_min": resolved.intensity_min,
            "intensity_max": resolved.intensity_max, "length": s.length, "emoji_usage": s.emoji_usage,
        },
        "intensity": resolved.adjustments.get("intensity", resolved.intensity_target),
        "strategy": strategy,
        "flow": flow,
        "topic_name": topic.name.lower() if topic else "este tema",
        "topic_slug": topic.slug if topic else None,
        "post_text": post_text,
        "facts": [fact_dict(f) for f in facts],
        "key_messages": key_msgs,
        "mandatory_vocab": resolved.mandatory_terms,
        "prohibited_vocab": resolved.prohibited_terms,
        "claims": claims or [],
        "complaint": complaint,
        "format_name": format_name,
        "closing_phrase": closing_phrase,
        "account_handle": account_handle,
        "variant": variant,
        "learning": learning or {},
        "max_facts": max_facts,
    }


def segments_text(segments: list[dict[str, Any]], legends: list[str] | None = None) -> str:
    body = " ".join(s["text"].strip() for s in segments if s.get("text"))
    if legends:
        body = body + "\n\n" + "\n".join(legends)
    return body.strip()
