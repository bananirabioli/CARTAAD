"""Everything a validator needs about a piece, gathered once."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.models.core import Client
from app.models.generation import ConsentRecord, Piece
from app.models.kb import Actor, ApprovedImage, Fact
from app.models.monitoring import OwnedAccount
from app.models.ops import RestrictionMode
from app.models.styles import CreativeType, Format, Style
from app.services.catalog import active_style, compat, get_creative, get_format
from app.services.client_settings import ClientSettings, get_client_settings
from app.services.style_resolver import ResolvedStyle, resolve
from app.services.veda import active_restriction

QUOTE_SLOTS = {"mito", "cita_original"}  # quotations of the original post, not our assertions


@dataclass
class Unit:
    location: str
    text: str
    fact_ids: list[int]
    seg_type: str | None = None
    quoted: bool = False


@dataclass
class PieceContext:
    piece: Piece
    client: Client
    settings: ClientSettings
    style: Style | None
    resolved: ResolvedStyle | None
    fmt: Format | None
    creative: CreativeType | None
    compat_level: str
    compat_note: str
    account: OwnedAccount | None
    veda: RestrictionMode | None
    facts: dict[int, Fact]
    actors: list[Actor]
    images: dict[int, ApprovedImage]
    consent: ConsentRecord | None
    topic: str | None
    now: datetime = field(default_factory=utcnow)

    def units(self) -> list[Unit]:
        c = self.piece.content or {}
        if self.piece.kind == "copy":
            return [Unit(f"segmento {i + 1}", s.get("text", ""), list(s.get("fact_ids") or []), s.get("type")) for i, s in enumerate(c.get("segments") or [])]
        out = []
        for name, slot in (c.get("slots") or {}).items():
            out.append(Unit(f"slot {name}", slot.get("text", ""), list(slot.get("fact_ids") or []), quoted=name in QUOTE_SLOTS))
        for i, slide in enumerate(c.get("slides") or []):
            out.append(Unit(f"lámina {i + 1} (título)", slide.get("title", ""), list(slide.get("fact_ids") or [])))
            out.append(Unit(f"lámina {i + 1}", slide.get("text", ""), list(slide.get("fact_ids") or [])))
        return out

    def visible_text(self, include_sources: bool = False, include_label: bool = True) -> str:
        c = self.piece.content or {}
        parts = [u.text for u in self.units() if u.text]
        parts += [(c.get("label") or "") if include_label else "", *(c.get("legends") or [])]
        if include_sources:
            parts += c.get("sources") or []
        return "\n".join(p for p in parts if p)

    def cited_fact_ids(self) -> set[int]:
        ids = {i for u in self.units() for i in u.fact_ids}
        comp = (self.piece.content or {}).get("comparison") or {}
        return ids | set(comp.get("left") or []) | set(comp.get("right") or [])


def build_context(db: Session, piece: Piece) -> PieceContext:
    from app.models.cases import Case

    client = db.get(Client, piece.client_id)
    case = db.get(Case, piece.case_id)
    style = db.get(Style, piece.style_id) if piece.style_id else active_style(db, client.id, piece.style_slug)
    resolved = resolve(db, client.id, style, topic=case.topic_slug if case else None, format_slug=piece.format_slug, account_id=piece.account_id, flow=piece.flow, adjustments={"intensity": piece.intensity}) if style else None
    creative = get_creative(db, client.id, piece.creative_slug) if piece.creative_slug else None
    level, note = compat(db, client.id, piece.creative_slug, piece.format_slug) if piece.creative_slug else ("full", "")
    content = piece.content or {}
    ids = {i for s in content.get("segments") or [] for i in s.get("fact_ids") or []}
    ids |= {i for s in (content.get("slots") or {}).values() for i in s.get("fact_ids") or []}
    ids |= {i for s in content.get("slides") or [] for i in s.get("fact_ids") or []}
    comp = content.get("comparison") or {}
    ids |= set(comp.get("left") or []) | set(comp.get("right") or [])
    facts = {f.id: f for f in db.scalars(select(Fact).where(Fact.client_id == client.id, Fact.id.in_(ids)))} if ids else {}
    image_ids = [i["approved_image_id"] for i in content.get("images") or [] if i.get("approved_image_id")]
    images = {i.id: i for i in db.scalars(select(ApprovedImage).where(ApprovedImage.client_id == client.id, ApprovedImage.id.in_(image_ids)))} if image_ids else {}
    consent = db.scalar(select(ConsentRecord).where(ConsentRecord.piece_id == piece.id).order_by(ConsentRecord.id.desc()))
    return PieceContext(
        piece=piece, client=client, settings=get_client_settings(client), style=style, resolved=resolved, fmt=get_format(db, client.id, piece.format_slug),
        creative=creative, compat_level=level, compat_note=note, account=db.get(OwnedAccount, piece.account_id) if piece.account_id else None,
        veda=active_restriction(db, client.id), facts=facts, actors=list(db.scalars(select(Actor).where(Actor.client_id == client.id))), images=images,
        consent=consent, topic=case.topic_slug if case else None,
    )


def fact_years(fact: Fact) -> set[int]:
    from app.validators.numbers import extract_figures

    years: set[int] = set()
    if fact.period_start and fact.period_end:
        years |= set(range(fact.period_start.year, fact.period_end.year + 1))
    for d in (fact.period_start, fact.period_end, fact.fact_date):
        if d:
            years.add(d.year)
    texts = [fact.statement, fact.period_label, fact.document.title if fact.document else ""]
    for text in texts:
        years |= {int(f.value) for f in extract_figures(text) if f.kind in ("year", "date") and f.value}
    if fact.document and fact.document.issued_at:
        years.add(fact.document.issued_at.year)
    return years


def describe(obj: Any) -> str:
    return getattr(obj, "code", None) or str(obj)
