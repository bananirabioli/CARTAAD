"""Runs every validator on a piece (before it reaches the inbox and again on every new version)."""

from typing import Any

from sqlalchemy.orm import Session

from app.guardrails.hard_rules import requires_legal_review
from app.i18n import t
from app.models.generation import FigureCheck, Piece
from app.services.actors import mentioned_actors
from app.validators.claims import validate_claims
from app.validators.common import status_of
from app.validators.compat import validate_compat
from app.validators.context import PieceContext, build_context
from app.validators.labels import validate_labels
from app.validators.numeric import validate_numeric
from app.validators.style_lint import lint

LOCKED = ("aprobado", "programado", "publicado", "descartado")


def _sync_figures(db: Session, piece: Piece, records: list[dict[str, Any]]) -> None:
    """Keep human verifications for identical figures of the same version; anything else starts as pending."""
    previous = {(f.raw, f.location): f for f in piece.figures if f.piece_version == piece.current_version}
    for fig in list(piece.figures):
        db.delete(fig)
    db.flush()
    piece.figures.clear()
    for r in records:
        old = previous.get((r["raw"], r["location"]))
        fig = FigureCheck(piece_id=piece.id, piece_version=piece.current_version, **r)
        if old and old.status != "pendiente" and old.fact_id == r["fact_id"]:
            fig.status, fig.verified_by_id, fig.verified_at = old.status, old.verified_by_id, old.verified_at
        piece.figures.append(fig)
        db.add(fig)


def _legal(ctx: PieceContext) -> tuple[bool, str]:
    style = ctx.style
    satirical = bool(style and ("satirico" in (style.tags or {}).get("humor", []) or "satirico" in (style.tags or {}).get("tono", [])))
    actors = [a for a in mentioned_actors(ctx.actors, ctx.visible_text()) if not a.is_own]
    required = requires_legal_review(bool(style and style.requires_legal), satirical, bool(actors))
    if not required:
        return False, ""
    reasons = []
    if style and style.requires_legal:
        reasons.append(t("pieces.legal.style", style=style.slug))
    if satirical and actors:
        reasons.append(t("pieces.legal.satire_actor", actor=actors[0].name))
    return True, " ".join(reasons)


def validate_piece(db: Session, piece: Piece) -> str:
    ctx = build_context(db, piece)
    findings = []
    numeric, figures = validate_numeric(ctx)
    findings += numeric
    findings += validate_claims(ctx)
    findings += validate_compat(ctx)
    findings += validate_labels(ctx)
    lint_status, lint_findings = ("ok", [])
    if ctx.resolved:
        lint_status, lint_findings = lint(ctx.visible_text(include_label=False), ctx.resolved, piece_kind=piece.kind)
    findings += lint_findings
    piece.validation = [f.as_dict() for f in findings]
    piece.validation_status = status_of(findings)
    piece.compliance = {"status": lint_status, "findings": [f.as_dict() for f in lint_findings], "style": piece.style_slug, "style_version": piece.style_version}
    _sync_figures(db, piece, figures)
    required, reason = _legal(ctx)
    if required and not piece.legal_required:
        piece.legal_required, piece.legal_status, piece.legal_reason = True, "pendiente", reason
    elif required:
        piece.legal_reason = reason
    elif not required and piece.legal_status == "pendiente":
        piece.legal_required, piece.legal_status, piece.legal_reason = False, "no_requerida", ""
    if piece.status not in LOCKED:
        piece.status = "bloqueado" if piece.validation_status == "block" else "generado"
    db.flush()
    return piece.validation_status
