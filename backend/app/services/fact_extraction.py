"""AI-assisted fact base: extract_facts proposes facts from a source document; a person approves them before use.

Proposed facts are stored as Fact(status="propuesto") linked to their document, with the literal quote and page, so the
reviewer sees where each one comes from. Only status="activo" facts reach the analysis and generation prompts.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.runner import StepMeta, run_step
from app.api.deps import next_code
from app.errors import AppError
from app.models.core import Client, Topic, User
from app.models.kb import Fact, SourceDocument
from app.services import audit
from app.services.client_settings import get_client_settings
from app.services.documents import index_document
from app.services.facts import refresh_embedding
from app.textnorm import normalize

MAX_TEXT_CHARS = 45_000
MAX_FACTS = 25


def document_text(doc: SourceDocument) -> str:
    pages: dict[int, list[str]] = {}
    for chunk in doc.chunks:
        pages.setdefault(chunk.page, []).append(chunk.text)
    text = "\n".join(f"[página {p}]\n" + " ".join(parts) for p, parts in sorted(pages.items()))
    return text[:MAX_TEXT_CHARS]


def _date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip()[:10]) if value and value.strip() else None
    except ValueError:
        return None


def extract_facts_from_document(db: Session, doc: SourceDocument, user: User | None, model: str | None = None) -> dict[str, Any]:
    if doc.status not in ("procesado",) or not doc.chunks:
        raise AppError(409, "conflict", "El documento todavía no tiene texto procesado (o es un PDF escaneado sin texto).")
    client = db.get(Client, doc.client_id)
    topics = list(db.scalars(select(Topic).where(Topic.client_id == client.id, Topic.active.is_(True))))
    ctx = {
        "client_name": client.name, "client_context": get_client_settings(client).context, "title": doc.title, "issuer": doc.issuer,
        "issued_at": doc.issued_at.date().isoformat() if doc.issued_at else "", "topics": [{"slug": t.slug, "name": t.name} for t in topics],
        "text": document_text(doc), "max_facts": MAX_FACTS,
    }
    out, run = run_step(db, "extract_facts", ctx, StepMeta(client_id=client.id, user_id=user.id if user else None), model=model)
    by_slug = {t.slug: t.id for t in topics}
    existing = {normalize(f.statement) for f in db.scalars(select(Fact).where(Fact.client_id == client.id, Fact.document_id == doc.id))}
    created: list[Fact] = []
    for item in out.facts[:MAX_FACTS]:  # type: ignore[attr-defined]
        statement = item.statement.strip()
        if len(statement) < 5 or normalize(statement) in existing:
            continue
        fact = Fact(
            client_id=client.id, code=next_code(db, client.id, "fact", "H"), statement=statement, value=item.value, unit=item.unit[:60],
            base=(item.base or "total")[:120], period_label=item.period_label[:120], fact_date=_date(item.fact_date) or doc.issued_at,
            document_id=doc.id, topic_id=by_slug.get(item.topic) or doc.topic_id, gov_level_id=doc.gov_level_id, status="propuesto",
            source_quote=item.quote[:1000], source_page=item.page, notes=f"Propuesto por IA ({run.model}) · revisar antes de usar",
        )
        refresh_embedding(fact)
        db.add(fact)
        existing.add(normalize(statement))
        created.append(fact)
    db.flush()
    audit.record(db, action="fact.extract", entity_type="document", entity_id=doc.id, client_id=client.id, user=user,
                 after={"proposed": len(created), "model": run.model, "ai_run_id": run.id}, note=doc.title)
    return {"document_id": doc.id, "proposed": len(created), "fact_ids": [f.id for f in created], "notes": out.notes, "model": run.model}  # type: ignore[attr-defined]


def document_from_text(db: Session, client_id: int, user: User | None, *, title: str, text: str, issuer: str = "", url: str | None = None,
                       issued_at: datetime | None = None, topic_id: int | None = None) -> SourceDocument:
    """A pasted text (press release, report excerpt, web page) becomes a source document, chunked and searchable."""
    doc = SourceDocument(client_id=client_id, title=title.strip()[:300], issuer=issuer.strip()[:200], doc_type="texto", url=url, issued_at=issued_at,
                         topic_id=topic_id, status="pendiente", created_by_id=user.id if user else None)
    db.add(doc)
    db.flush()
    pages = [p.strip() for p in text.split("\f") if p.strip()] or [text.strip()]
    index_document(db, doc, pages)
    db.refresh(doc)
    return doc


def quick_source(db: Session, client_id: int, user: User | None, *, title: str, issuer: str | None, url: str | None, date: datetime | None) -> SourceDocument:
    """Manual facts with a source but no PDF: reuse a document with the same title or create a light one."""
    title = title.strip()
    doc = db.scalar(select(SourceDocument).where(SourceDocument.client_id == client_id, SourceDocument.title == title))
    if doc:
        return doc
    doc = SourceDocument(client_id=client_id, title=title[:300], issuer=(issuer or "").strip()[:200], doc_type="referencia", url=url, issued_at=date,
                         status="procesado", created_by_id=user.id if user else None)
    db.add(doc)
    db.flush()
    return doc
