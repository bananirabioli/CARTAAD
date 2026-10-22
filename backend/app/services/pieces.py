"""Piece versions, manual edits, copilot, revert and per-figure verification.

Any new version (copilot or human) sends the piece back to `generado`, invalidates figure verifications and the
approval, and re-runs every validator (section 5). The copilot moves only inside the style limits and can never skip
validators, directives or hard rules.
"""

import difflib
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.runner import StepMeta, run_step
from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import check_text_against_hard_rules
from app.i18n import t
from app.models.cases import Case
from app.models.core import Client, Topic, User
from app.models.generation import FigureCheck, Piece, PieceVersion, Review
from app.models.kb import Fact
from app.models.monitoring import Post
from app.models.styles import Style
from app.services import audit
from app.services.cases import strategy_candidates, transition
from app.services.catalog import active_style, compat, format_style_slugs, get_creative, get_format, style_allowed_for_format
from app.services.client_settings import get_client_settings
from app.services.copy_context import build_copy_context, fact_dict, key_messages, relevant_facts
from app.services.generation import piece_tags, piece_visible_text, refresh_piece_risk, run_red_team, sources_for
from app.services.style_resolver import resolve
from app.validators.runner import validate_piece

LOCKED = ("programado", "publicado", "descartado")
COPILOT_ACTIONS = ("mas_corto", "mas_firme", "mas_formal", "menos_formal", "mas_empatico", "otro_angulo", "agregar_dato", "cambiar_estilo", "libre")
FLOW_STRATEGIES = {"A": ["contextualizar", "desmentir", "reencuadrar", "contrastar"], "B": ["amplificar", "agradecer"]}


def word_diff(old: str, new: str) -> list[dict[str, str]]:
    a, b = re.findall(r"\S+|\s+", old), re.findall(r"\S+|\s+", new)
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append({"op": "equal", "text": "".join(a[i1:i2])})
        else:
            if i2 > i1:
                ops.append({"op": "delete", "text": "".join(a[i1:i2])})
            if j2 > j1:
                ops.append({"op": "insert", "text": "".join(b[j1:j2])})
    return ops


def _content_text(kind: str, content: dict[str, Any]) -> str:
    probe = Piece(kind=kind, content=content)
    return piece_visible_text(probe)


def _facts_used(content: dict[str, Any]) -> set[int]:
    ids = {i for s in content.get("segments") or [] for i in s.get("fact_ids") or []}
    ids |= {i for s in (content.get("slots") or {}).values() for i in s.get("fact_ids") or []}
    ids |= {i for s in content.get("slides") or [] for i in s.get("fact_ids") or []}
    return ids


def _finalize_content(db: Session, piece: Piece, content: dict[str, Any], legends: list[str]) -> dict[str, Any]:
    used = _facts_used(content)
    facts = list(db.scalars(select(Fact).where(Fact.client_id == piece.client_id, Fact.id.in_(used)))) if used else []
    content["sources"] = sources_for(sorted(facts, key=lambda f: f.code))
    content["legends"] = legends
    return content


def _after_change(db: Session, piece: Piece, user: User | None, *, red_team: bool = True) -> None:
    case = db.get(Case, piece.case_id)
    was_approved = piece.status == "aprobado"
    if piece.status not in LOCKED:
        piece.status = "generado"
    piece.updated_at = utcnow()
    validate_piece(db, piece)  # re-runs every validator; figure checks restart for the new version
    if red_team:
        facts = list(db.scalars(select(Fact).where(Fact.client_id == piece.client_id, Fact.id.in_(_facts_used(piece.content))))) if _facts_used(piece.content) else []
        run_red_team(db, case, [piece], facts, user)
    refresh_piece_risk(db, case, piece)
    if was_approved and case.status == "aprobado":
        still = db.scalar(select(Piece.id).where(Piece.case_id == case.id, Piece.status == "aprobado", Piece.id != piece.id))
        if not still:
            transition(db, case, "en_revision", user, note=f"pieza {piece.id} modificada tras aprobación")
    elif case.status == "generado":
        transition(db, case, "en_revision", user, note=f"pieza {piece.id} modificada")
    if piece.kind == "creative":
        piece.render_status = "pendiente"
        db.flush()
        if _eager():
            from app.render.renderer import render_piece

            render_piece(db, piece)


def _eager() -> bool:
    from app.worker import celery_app

    return bool(celery_app.conf.task_always_eager)


def enqueue_pending_render(piece: Piece) -> None:
    """Call after commit: the worker renders the new version (HTML → PNG with Playwright)."""
    if piece.kind == "creative" and piece.render_status == "pendiente" and not _eager():
        from app.tasks import render_piece_task

        render_piece_task.delay(piece.id)


def new_version(
    db: Session, piece: Piece, user: User | None, content: dict[str, Any], *, author_type: str, action: str, instruction: str = "", note: str = "",
    style: Style | None = None, intensity: int | None = None, strategy: str | None = None, ai_run_id: int | None = None,
) -> PieceVersion:
    if piece.status in LOCKED:
        raise AppError(409, "conflict", t("pieces.errors.locked", status=piece.status))
    old_text = _content_text(piece.kind, piece.content or {})
    new_text = _content_text(piece.kind, content)
    if style is not None and style.id != piece.style_id:
        fmt = get_format(db, piece.client_id, piece.format_slug)
        piece.style_id, piece.style_slug, piece.style_version = style.id, style.slug, style.version
        piece.effective_tags = piece_tags(style, fmt, strategy or piece.strategy, piece.flow, "ilustracion" in (piece.effective_tags or []))
    if intensity is not None:
        piece.intensity = intensity
    if strategy is not None:
        piece.strategy = strategy
    piece.current_version += 1
    piece.content = content
    version = PieceVersion(
        piece_id=piece.id, version=piece.current_version, content=content, style_slug=piece.style_slug, style_version=piece.style_version, strategy=piece.strategy,
        intensity=piece.intensity, author_type=author_type, author_id=user.id if user else None, action=action, instruction=instruction,
        diff=word_diff(old_text, new_text), note=note, ai_run_id=ai_run_id,
    )
    db.add(version)
    db.flush()
    return version


def _suggest_style(db: Session, piece: Piece, predicate) -> Style | None:  # noqa: ANN001
    fmt = get_format(db, piece.client_id, piece.format_slug)
    for slug in format_style_slugs(fmt):
        st = active_style(db, piece.client_id, slug)
        if st and slug != piece.style_slug and style_allowed_for_format(st, fmt) and predicate(st):
            return st
    return None


def run_copilot(db: Session, piece: Piece, user: User, *, action: str, instruction: str = "", style_slug: str | None = None) -> dict[str, Any]:
    if action not in COPILOT_ACTIONS:
        raise AppError(422, "invalid_value", detail=action)
    if piece.status in LOCKED:
        raise AppError(409, "conflict", t("pieces.errors.locked", status=piece.status))
    hits = check_text_against_hard_rules(instruction) if instruction else []
    if hits:
        return {"applied": False, "message": t("pieces.copilot.hard_rule", rule=hits[0].rule_id, message=hits[0].message), "rule_id": hits[0].rule_id}
    case = db.get(Case, piece.case_id)
    client = db.get(Client, piece.client_id)
    settings = get_client_settings(client)
    fmt = get_format(db, client.id, piece.format_slug)
    style = db.get(Style, piece.style_id) if piece.style_id else active_style(db, client.id, piece.style_slug)
    target_style, strategy, register_target, add_fact = style, piece.strategy, None, None
    resolved = resolve(db, client.id, style, topic=case.topic_slug, format_slug=fmt.slug, account_id=piece.account_id, flow=piece.flow)
    intensity = max(resolved.intensity_min, min(piece.intensity, resolved.intensity_max))
    registers = set((style.tags or {}).get("registro") or [])

    if action == "mas_firme":
        if intensity + 1 > resolved.intensity_max:
            alt = _suggest_style(db, piece, lambda st: st.intensity_max > resolved.intensity_max)
            msg = t("pieces.copilot.intensity_max", style=style.slug, max=resolved.intensity_max, suggested=alt.slug) if alt else t("pieces.copilot.intensity_max_no_alt", style=style.slug, max=resolved.intensity_max)
            return {"applied": False, "message": msg, "suggested_style": alt.slug if alt else None}
        intensity += 1
    elif action == "mas_empatico":
        intensity = max(resolved.intensity_min, intensity - 1)
    elif action in ("mas_formal", "menos_formal"):
        wanted = {"formal"} if action == "mas_formal" else {"cotidiano", "coloquial"}
        if not registers & wanted and registers:
            alt = _suggest_style(db, piece, lambda st: bool(set((st.tags or {}).get("registro") or []) & wanted))
            target = "formal" if action == "mas_formal" else "cotidiano"
            msg = t("pieces.copilot.register", style=style.slug, current=", ".join(sorted(registers)), target=target, suggested=alt.slug) if alt else t("pieces.copilot.register_no_alt", style=style.slug, target=target)
            return {"applied": False, "message": msg, "suggested_style": alt.slug if alt else None}
        register_target = "formal" if action == "mas_formal" else ("cotidiano" if "cotidiano" in registers or not registers else "coloquial")
    elif action == "otro_angulo":
        options = strategy_candidates(settings, case.stance, case.message_type) + FLOW_STRATEGIES.get(piece.flow, [])
        if case.message_type == "queja_ciudadana_legitima":
            options = [o for o in options if o in ("contextualizar", "agradecer")]
        others = [o for o in dict.fromkeys(options) if o != piece.strategy]
        if not others:
            return {"applied": False, "message": t("pieces.copilot.no_other_angle")}
        strategy = others[0]
    elif action == "agregar_dato":
        post = db.get(Post, case.post_id)
        topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))
        used = _facts_used(piece.content or {})
        candidates = [f for f in relevant_facts(db, client.id, post.text, topic.id if topic else None, limit=12) if f.id not in used and f.value is not None]
        if not candidates:
            return {"applied": False, "message": t("pieces.copilot.no_fact")}
        add_fact = candidates[0]
    elif action == "cambiar_estilo":
        target_style = active_style(db, client.id, style_slug) if style_slug else None
        if target_style is None or not style_allowed_for_format(target_style, fmt):
            raise AppError(422, "invalid_value", t("pieces.errors.style_not_allowed", style=style_slug or "", format=fmt.slug))
        if target_style.slug == style.slug:
            return {"applied": False, "message": t("pieces.copilot.same_style", style=style.slug)}
        resolved = resolve(db, client.id, target_style, topic=case.topic_slug, format_slug=fmt.slug, account_id=piece.account_id, flow=piece.flow)
        intensity = resolved.intensity_target
    elif action == "libre" and not instruction.strip():
        raise AppError(422, "invalid_value", detail="instruction")

    resolved = resolve(db, client.id, target_style, topic=case.topic_slug, format_slug=fmt.slug, account_id=piece.account_id, flow=piece.flow, adjustments={"intensity": intensity})
    post = db.get(Post, case.post_id)
    topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))
    facts = relevant_facts(db, client.id, post.text, topic.id if topic else None, limit=6)
    claims = [{"text": c.text, "verdict": c.verdict} for c in (case.interpretation.claims if case.interpretation else [])]
    ctx = build_copy_context(
        client=client, resolved=resolved, strategy=strategy, flow=piece.flow, topic=topic, post_text=post.text, facts=facts, key_msgs=key_messages(db, client.id, topic.id if topic else None),
        claims=claims, complaint=case.message_type == "queja_ciudadana_legitima", format_name=fmt.name, closing_phrase=(fmt.options or {}).get("closing_phrase"),
    )
    creative = get_creative(db, client.id, piece.creative_slug) if piece.creative_slug else None
    level, note = compat(db, client.id, piece.creative_slug, fmt.slug) if creative else ("full", "")
    ctx.update(
        piece={"kind": piece.kind, "content": piece.content, "text_only": bool(creative and creative.text_only)}, action=action, instruction=instruction, target_intensity=intensity,
        register_target=register_target, add_fact=fact_dict(add_fact) if add_fact else None,
        creative={"slug": creative.slug, "name": creative.name, "level": level, "note": note, "required_slots": creative.required_slots, "template": creative.template, "requires_fact": creative.requires_fact} if creative else None,
        images=[], variant=piece.current_version,
    )
    out, run = run_step(db, "refine_piece", ctx, StepMeta(client_id=client.id, user_id=user.id, case_id=case.id, piece_id=piece.id, style_id=target_style.id, style_slug=target_style.slug,
                                                          style_version=target_style.version, applied_directives=resolved.trace()))
    if out.refused:  # type: ignore[attr-defined]
        return {"applied": False, "message": out.refusal_reason or out.note, "suggested_style": out.suggested_style}  # type: ignore[attr-defined]
    valid_ids = {f.id for f in facts} | ({add_fact.id} if add_fact else set()) | _facts_used(piece.content or {})
    content = dict(piece.content or {})
    if piece.kind == "copy":
        content["segments"] = [{**s.model_dump(), "fact_ids": [i for i in s.fact_ids if i in valid_ids]} for s in out.segments]  # type: ignore[attr-defined]
    else:
        if out.slots:  # type: ignore[attr-defined]
            content["slots"] = {s.name: {"text": s.text, "fact_ids": [i for i in s.fact_ids if i in valid_ids]} for s in out.slots}  # type: ignore[attr-defined]
        content["slides"] = [{"title": s.title, "text": s.text, "fact_ids": [i for i in s.fact_ids if i in valid_ids]} for s in out.slides] or content.get("slides", [])  # type: ignore[attr-defined]
        content["headline"] = (content.get("slots", {}).get("titulo") or {}).get("text", content.get("headline", ""))
    content = _finalize_content(db, piece, content, resolved.legend_texts)
    version = new_version(db, piece, user, content, author_type="ia", action=action, instruction=instruction, note=out.note, style=target_style, intensity=intensity, strategy=strategy, ai_run_id=run.id)  # type: ignore[attr-defined]
    db.add(Review(client_id=piece.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=user.id, action="copiloto", piece_version=version.version, note=f"{action}: {instruction}".strip(": ")))
    audit.record(db, action="piece.copilot", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, after={"version": version.version, "action": action, "instruction": instruction})
    _after_change(db, piece, user)
    return {"applied": True, "message": out.note, "version": version.version}  # type: ignore[attr-defined]


def edit_piece(db: Session, piece: Piece, user: User, content_in: dict[str, Any], note: str = "") -> PieceVersion:
    """Manual edit by a person (text slots / segments only; facts must still be cited)."""
    case = db.get(Case, piece.case_id)
    style = db.get(Style, piece.style_id) if piece.style_id else None
    resolved = resolve(db, piece.client_id, style, topic=case.topic_slug, format_slug=piece.format_slug, account_id=piece.account_id, flow=piece.flow) if style else None
    content = dict(piece.content or {})
    if piece.kind == "copy" and "segments" in content_in:
        content["segments"] = [{"text": str(s.get("text", "")), "type": s.get("type", "opinion_marcada"), "fact_ids": [int(i) for i in s.get("fact_ids") or []]} for s in content_in["segments"]]
    if piece.kind == "creative":
        if "slots" in content_in:
            content["slots"] = {k: {"text": str(v.get("text", "")), "fact_ids": [int(i) for i in v.get("fact_ids") or []]} for k, v in content_in["slots"].items()}
            content["headline"] = (content["slots"].get("titulo") or {}).get("text", content.get("headline", ""))
        if "slides" in content_in:
            content["slides"] = [{"title": str(s.get("title", "")), "text": str(s.get("text", "")), "fact_ids": [int(i) for i in s.get("fact_ids") or []]} for s in content_in["slides"]]
        if "images" in content_in:
            content["images"] = content_in["images"]
    content = _finalize_content(db, piece, content, resolved.legend_texts if resolved else content.get("legends", []))
    version = new_version(db, piece, user, content, author_type="persona", action="editar", note=note)
    db.add(Review(client_id=piece.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=user.id, action="editar", piece_version=version.version, note=note))
    audit.record(db, action="piece.edit", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, after={"version": version.version})
    _after_change(db, piece, user)
    return version


def revert_piece(db: Session, piece: Piece, user: User, version_number: int) -> PieceVersion:
    target = next((v for v in piece.versions if v.version == version_number), None)
    if target is None:
        raise AppError(404, "not_found", t("pieces.errors.version_missing", version=version_number))
    style = db.scalar(select(Style).where(Style.client_id == piece.client_id, Style.slug == target.style_slug, Style.version == target.style_version)) or db.get(Style, piece.style_id)
    version = new_version(db, piece, user, dict(target.content), author_type="persona", action="revertir", instruction=f"revertir a v{version_number}", style=style, intensity=target.intensity, strategy=target.strategy)
    audit.record(db, action="piece.revert", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, after={"version": version.version, "from": version_number})
    _after_change(db, piece, user)
    return version


def verify_figure(db: Session, piece: Piece, figure: FigureCheck, user: User, status: str, note: str = "") -> FigureCheck:
    if figure.piece_id != piece.id or figure.piece_version != piece.current_version:
        raise AppError(409, "conflict", t("pieces.errors.figure_wrong_version"))
    if piece.status in LOCKED:
        raise AppError(409, "conflict", t("pieces.errors.locked", status=piece.status))
    figure.status, figure.verified_by_id, figure.verified_at = status, user.id, utcnow()
    db.add(Review(client_id=piece.client_id, piece_id=piece.id, case_id=piece.case_id, user_id=user.id, action="verificar_cifra", piece_version=piece.current_version, note=f"{figure.raw}: {status} {note}".strip()))
    audit.record(db, action="figure.verify", entity_type="piece", entity_id=piece.id, client_id=piece.client_id, user=user, after={"figure": figure.raw, "status": status, "version": piece.current_version})
    case = db.get(Case, piece.case_id)
    if case.status == "generado":
        transition(db, case, "en_revision", user, note="verificación de cifras")
    refresh_piece_risk(db, case, piece)
    return figure
