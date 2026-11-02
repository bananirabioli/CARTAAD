"""Approval (HR-09), simulated scheduling/publishing (HR-02, HR-04, HR-09), exports and ally packages.

Nothing here talks to a real social network. Publishing is simulated and only towards registered accounts.
"""

import io
import json
import secrets
import zipfile
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import HardRuleViolation, PieceGate, assert_approvable, assert_not_restricted, assert_publishable, assert_registered_account
from app.i18n import t
from app.models.cases import Case
from app.models.core import User
from app.models.generation import ConsentRecord, Piece, Review
from app.models.kb import Fact
from app.models.monitoring import OwnedAccount
from app.models.ops import RestrictionMode
from app.models.publishing import AllyPackage, AllyShare, ScheduledPost
from app.models.styles import CreativeType
from app.services import audit
from app.services.cases import transition
from app.services.facts import fact_label
from app.storage import get_storage


def gate_for(piece: Piece) -> PieceGate:
    return PieceGate(
        status=piece.status, current_version=piece.current_version, approved_version=piece.approved_version, figures_total=len(piece.figures),
        figures_verified=sum(1 for f in piece.figures if f.status == "verificada"), blocking_findings=sum(1 for f in piece.validation if f.get("severity") == "block"),
        legal_required=piece.legal_required, legal_status=piece.legal_status,
    )


def approval_blockers(db: Session, piece: Piece) -> list[str]:
    blockers = []
    try:
        assert_approvable(gate_for(piece))
    except HardRuleViolation as exc:
        blockers.append(f"{exc.rule_id}: {exc.message}")
    if piece.legal_required and piece.legal_status != "liberada" and not any("legal" in b.lower() for b in blockers):
        blockers.append(t("publishing.blockers.legal"))
    if piece.missing_inputs:
        blockers.append(t("publishing.blockers.missing_inputs", items="; ".join(piece.missing_inputs)))
    ct = db.scalar(select(CreativeType).where(CreativeType.client_id == piece.client_id, CreativeType.slug == piece.creative_slug)) if piece.creative_slug else None
    if ct and ct.requires_consent and not db.scalar(select(ConsentRecord.id).where(ConsentRecord.piece_id == piece.id)):
        blockers.append(t("publishing.blockers.consent"))
    if any(f.status == "rechazada" for f in piece.figures):
        blockers.append(t("publishing.blockers.rejected_figures"))
    if piece.render_status in ("pendiente", "generando", "error"):
        blockers.append(t("publishing.blockers.render", status=piece.render_status))
    return blockers


def approve(db: Session, piece: Piece, user: User, note: str = "") -> Piece:
    blockers = approval_blockers(db, piece)
    if blockers:
        rule = blockers[0].split(":")[0] if blockers[0].startswith("HR-") else "HR-09"
        raise AppError(409, "not_approvable", t("publishing.not_approvable"), details={"blockers": blockers, "rule_id": rule})
    piece.status, piece.approved_version, piece.approved_by_id, piece.approved_at = "aprobado", piece.current_version, user.id, utcnow()
    db.add(Review(client_id=piece.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=user.id, action="aprobar", piece_version=piece.current_version, note=note))
    audit.record(db, action="piece.approve", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, after={"version": piece.current_version}, note=note)
    case = db.get(Case, piece.case_id)
    if case.status == "generado":
        transition(db, case, "en_revision", user, note="revisión")
    if case.status == "en_revision":
        transition(db, case, "aprobado", user, note=f"pieza {piece.id} aprobada")
    return piece


def discard(db: Session, piece: Piece, user: User, reason: str) -> Piece:
    if len(reason.strip()) < 3:
        raise AppError(422, "invalid_value", t("cases.reason_required"))
    if piece.status in ("programado", "publicado"):
        raise AppError(409, "conflict", t("pieces.errors.locked", status=piece.status))
    piece.status, piece.discard_reason = "descartado", reason.strip()
    db.add(Review(client_id=piece.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=user.id, action="descartar", piece_version=piece.current_version, note=reason))
    audit.record(db, action="piece.discard", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, note=reason)
    return piece


def _facts(db: Session, piece: Piece) -> list[Fact]:
    c = piece.content or {}
    ids = {i for s in c.get("segments") or [] for i in s.get("fact_ids") or []}
    ids |= {i for s in (c.get("slots") or {}).values() for i in s.get("fact_ids") or []}
    ids |= {i for s in c.get("slides") or [] for i in s.get("fact_ids") or []}
    return list(db.scalars(select(Fact).where(Fact.id.in_(ids)))) if ids else []


def publication_text(db: Session, piece: Piece, copy_piece: Piece | None = None) -> str:
    """Final text that would go out: copy + mandatory legends + visible sources (HR-01)."""
    source = copy_piece or (piece if piece.kind == "copy" else None)
    body = " ".join(s["text"] for s in (source.content.get("segments") or [])) if source else (piece.content.get("headline") or "")
    legends = list(dict.fromkeys((source.content.get("legends") if source else None) or piece.content.get("legends") or []))
    facts = {f.id: f for f in [*_facts(db, piece), *(_facts(db, source) if source and source is not piece else [])]}
    sources = [f"{f.code} · {fact_label(f)}" for f in facts.values()]
    parts = [body.strip(), *legends]
    if sources:
        parts.append("Fuentes: " + " | ".join(sources))
    return "\n\n".join(p for p in parts if p)


def _check_publishable(db: Session, piece: Piece, account: OwnedAccount, when: datetime) -> None:
    assert_registered_account(account, piece.client_id)  # HR-02
    assert_publishable(gate_for(piece))  # HR-09
    for r in db.scalars(select(RestrictionMode).where(RestrictionMode.client_id == piece.client_id)):
        assert_not_restricted(r, when, format_slug=account.format_slug, creative_slug=piece.creative_slug)  # HR-04


def schedule(db: Session, user: User, client_id: int, *, piece: Piece, account_id: int, scheduled_at: datetime, copy_piece: Piece | None = None) -> ScheduledPost:
    account = db.get(OwnedAccount, account_id)
    if account is None or account.client_id != client_id:
        raise HardRuleViolation("HR-02", t("hard_rules.HR-02.unregistered_account"))
    if copy_piece is not None:
        if copy_piece.case_id != piece.case_id or copy_piece.kind != "copy":
            raise AppError(422, "invalid_value", detail="copy_piece_id")
        assert_publishable(gate_for(copy_piece))
    _check_publishable(db, piece, account, scheduled_at)
    sp = ScheduledPost(
        client_id=client_id, case_id=piece.case_id, piece_id=piece.id, copy_piece_id=copy_piece.id if copy_piece else None, piece_version=piece.current_version,
        account_id=account.id, scheduled_at=scheduled_at, text=publication_text(db, piece, copy_piece), created_by_id=user.id,
    )
    db.add(sp)
    db.flush()
    piece.status = "programado"
    case = db.get(Case, piece.case_id)
    if case.status == "aprobado":
        transition(db, case, "programado", user, note=f"{account.handle} · {scheduled_at.isoformat()}")
    audit.record(db, action="schedule.create", entity_type="scheduled_post", entity_id=sp.id, client_id=client_id, user=user, after={"piece_id": piece.id, "account": account.handle, "at": scheduled_at.isoformat()})
    return sp


def cancel(db: Session, sp: ScheduledPost, user: User, reason: str = "") -> ScheduledPost:
    if sp.status != "programado":
        raise AppError(409, "conflict", detail=sp.status)
    sp.status, sp.error = "cancelado", reason
    piece = db.get(Piece, sp.piece_id)
    if piece.status == "programado":
        piece.status = "aprobado"
    case = db.get(Case, sp.case_id)
    others = db.scalar(select(ScheduledPost.id).where(ScheduledPost.case_id == case.id, ScheduledPost.status == "programado", ScheduledPost.id != sp.id))
    if case.status == "programado" and not others:
        transition(db, case, "aprobado", user, note="programación cancelada")
    audit.record(db, action="schedule.cancel", entity_type="scheduled_post", entity_id=sp.id, client_id=sp.client_id, user=user, note=reason)
    return sp


def publish(db: Session, sp: ScheduledPost, user: User | None = None, now: datetime | None = None) -> ScheduledPost:
    """Simulated publication. Gates are re-checked at publish time (a later copilot edit or a new veda stops it)."""
    now = now or utcnow()
    piece = db.get(Piece, sp.piece_id)
    account = db.get(OwnedAccount, sp.account_id)
    try:
        if piece.approved_version != sp.piece_version:
            raise HardRuleViolation("HR-09", t("hard_rules.HR-09.stale_approval"))
        _check_publishable(db, piece, account, now)
    except HardRuleViolation as exc:
        sp.status, sp.error = "error", f"{exc.rule_id}: {exc.message}"
        audit.record(db, action="schedule.blocked", entity_type="scheduled_post", entity_id=sp.id, client_id=sp.client_id, user=user, note=sp.error)
        return sp
    sp.status, sp.published_at, sp.external_ref = "publicado", now, f"sim-{secrets.token_hex(4)}"
    piece.status = "publicado"
    case = db.get(Case, sp.case_id)
    if case.status in ("programado", "aprobado"):
        transition(db, case, "publicado", user, note=f"publicación simulada en {account.handle}")
    audit.record(db, action="schedule.publish", entity_type="scheduled_post", entity_id=sp.id, client_id=sp.client_id, user=user, note=f"{account.handle} (simulado)")
    return sp


def publish_due(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    due = list(db.scalars(select(ScheduledPost).where(ScheduledPost.status == "programado", ScheduledPost.scheduled_at <= now)))
    for sp in due:
        publish(db, sp, None, now)
    return len(due)


# ------------------------------------------------------------------ export


def piece_spec(db: Session, piece: Piece) -> dict[str, Any]:
    case = db.get(Case, piece.case_id)
    return {
        "piece_id": piece.id, "case": case.code, "kind": piece.kind, "creative": piece.creative_slug, "format": piece.format_slug,
        "style": {"slug": piece.style_slug, "version": piece.style_version}, "strategy": piece.strategy, "intensity": piece.intensity,
        "effective_tags": piece.effective_tags, "applied_directives": piece.applied_directives, "adaptation": piece.adaptation, "why": piece.why,
        "version": piece.current_version, "approved_version": piece.approved_version, "content": piece.content,
        "facts": [{"id": f.id, "code": f.code, "statement": f.statement, "source": fact_label(f)} for f in _facts(db, piece)],
        "images_meta": [img.get("meta") for img in piece.content.get("images") or [] if img.get("generated")],
    }


def export_zip(db: Session, pieces: list[Piece]) -> bytes:
    buf = io.BytesIO()
    storage = get_storage()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for piece in pieces:
            folder = f"pieza-{piece.id}-{piece.creative_slug or 'copy'}-{piece.style_slug}"
            z.writestr(f"{folder}/spec.json", json.dumps(piece_spec(db, piece), ensure_ascii=False, indent=2, default=str))
            z.writestr(f"{folder}/copy.txt", publication_text(db, piece))
            for i, key in enumerate(piece.renders or [], start=1):
                if storage.exists(key):
                    z.writestr(f"{folder}/imagen-{i}.png", storage.read(key))
    return buf.getvalue()


# ------------------------------------------------------------------ ally packages


def create_ally_package(db: Session, user: User, case: Case, *, title: str, message: str, piece_ids: list[int], expires_in_days: int) -> AllyPackage:
    pieces = list(db.scalars(select(Piece).where(Piece.case_id == case.id, Piece.id.in_(piece_ids))))
    if not pieces or len(pieces) != len(set(piece_ids)):
        raise AppError(422, "invalid_value", detail="piece_ids")
    for p in pieces:
        if p.status not in ("aprobado", "programado", "publicado"):
            raise HardRuleViolation("HR-09", t("hard_rules.HR-09.not_approved"))
    copy_piece = next((p for p in pieces if p.kind == "copy"), None)
    pkg = AllyPackage(
        client_id=case.client_id, case_id=case.id, token=secrets.token_urlsafe(24), title=title, message=message,
        suggested_copy=publication_text(db, copy_piece) if copy_piece else "", piece_ids=[p.id for p in pieces],
        expires_at=utcnow() + timedelta(days=expires_in_days), created_by_id=user.id,
    )
    db.add(pkg)
    db.flush()
    audit.record(db, action="ally.create", entity_type="ally_package", entity_id=pkg.id, client_id=case.client_id, user=user, after={"pieces": pkg.piece_ids, "expires_at": pkg.expires_at.isoformat()})
    return pkg


def get_valid_package(db: Session, token: str) -> AllyPackage:
    pkg = db.scalar(select(AllyPackage).where(AllyPackage.token == token))
    if pkg is None or pkg.revoked or pkg.expires_at < utcnow():
        raise AppError(404, "not_found", t("publishing.package_expired"))
    return pkg


def record_share(db: Session, pkg: AllyPackage, *, account_id: int, shared_by_name: str, piece_id: int | None) -> AllyShare:
    account = db.get(OwnedAccount, account_id)
    if account is None or account.client_id != pkg.client_id or account.account_type not in ("aliada", "voceria"):
        raise HardRuleViolation("HR-02", t("hard_rules.HR-02.unregistered_account"))
    assert_registered_account(account, pkg.client_id)
    if piece_id is not None and piece_id not in pkg.piece_ids:
        raise AppError(422, "invalid_value", detail="piece_id")
    share = AllyShare(package_id=pkg.id, account_id=account.id, piece_id=piece_id, shared_by_name=shared_by_name.strip()[:200])
    db.add(share)
    audit.record(db, action="ally.shared", entity_type="ally_package", entity_id=pkg.id, client_id=pkg.client_id, note=f"{account.handle} · {shared_by_name}")
    return share
