"""Generation (6.5): copy in N style variants + 5–10 creatives filtered by the creative × format matrix and the veda.

Every piece stores its style (and version), effective tags, applied directives, adaptation and why. Validators run
before the piece reaches the inbox; the red team runs after, informative only.
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.images import build_image_spec, get_image_provider
from app.ai.runner import StepMeta, run_step
from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import assert_registered_account, restriction_active
from app.i18n import t
from app.models.cases import Case
from app.models.core import Client, Topic, User
from app.models.generation import Piece, PieceVersion, Proposal, RedTeamNote
from app.models.kb import ApprovedImage, Fact
from app.models.monitoring import OwnedAccount, Post
from app.models.styles import CreativeType, Format, Style
from app.services import audit
from app.services.cases import case_risk, facts_for_case, transition
from app.services.catalog import active_style, compat, creatives, format_style_slugs, get_format, style_allowed_for_format
from app.services.client_settings import get_client_settings
from app.services.copy_context import build_copy_context, fact_dict, key_messages, relevant_facts
from app.services.facts import fact_label, is_expired
from app.services.learning import learning_context
from app.services.style_resolver import ResolvedStyle, resolve
from app.services.veda import active_restriction
from app.storage import client_key, get_storage
from app.validators.runner import validate_piece

ILLUSTRATION_KIND = {"historieta": "panels", "titeres": "puppets", "voz_pueblo": "figures"}


# ------------------------------------------------------------------ helpers


def piece_tags(style: Style, fmt: Format, strategy: str, flow: str, illustrated: bool) -> list[str]:
    tags = [f"{dim}:{v}" for dim, vals in (style.tags or {}).items() for v in vals]
    tags += [f"estilo:{style.slug}", f"formato:{fmt.slug}", f"estrategia:{strategy}", f"flujo:{flow}", f"riesgo:{style.risk}"]
    if illustrated:
        tags.append("ilustracion")
    return tags


def sources_for(facts: list[Fact]) -> list[str]:
    return [f"{f.code} · {fact_label(f)}" for f in facts]


def variant_styles(db: Session, client: Client, fmt: Format, chosen: str | None) -> list[Style]:
    settings = get_client_settings(client)
    allowed = [s for s in format_style_slugs(fmt) if (st := active_style(db, client.id, s)) and style_allowed_for_format(st, fmt)]
    order = [chosen] if chosen else []
    order += [s for s in settings.default_variant_styles if s in allowed]
    order += allowed
    slugs: list[str] = []
    for s in order:
        if s and s in allowed and s not in slugs:
            slugs.append(s)
    return [active_style(db, client.id, s) for s in slugs[:3]]


def _photos(db: Session, client_id: int, topic_id: int | None) -> list[ApprovedImage]:
    rows = list(db.scalars(select(ApprovedImage).where(ApprovedImage.client_id == client_id, ApprovedImage.image_type == "foto_real", ApprovedImage.approved.is_(True))))
    usable = [i for i in rows if i.credit.strip() and (topic_id is None or i.topic_id in (topic_id, None))] or [i for i in rows if i.credit.strip()]
    return sorted(usable, key=lambda i: "antes" in (i.tags or []))  # «after» / neutral photos first for hero images


def select_creatives(db: Session, client: Client, flow: str, fmt: Format, has_facts: bool, photos: list[ApprovedImage], learning: dict[str, Any]) -> tuple[list[tuple[CreativeType, str, str]], list[dict[str, Any]]]:
    settings = get_client_settings(client)
    veda = active_restriction(db, client.id)
    selected, excluded = [], []
    rank = {g["value"]: (g["rate"], g["n"]) for g in learning.get("creatives", [])}
    tags = {t_ for p in photos for t_ in (p.tags or [])}
    for ct in creatives(db, client.id, flow):
        level, note = compat(db, client.id, ct.slug, fmt.slug)
        if level == "none":
            excluded.append({"slug": ct.slug, "reason": note or t("validators.compat.not_in_matrix"), "kind": "matriz"})
        elif veda and restriction_active(veda, utcnow()) and ct.slug in (veda.blocked_creatives or []):
            excluded.append({"slug": ct.slug, "reason": t("validators.compat.veda_creative", creative=ct.slug, name=veda.name), "kind": "veda"})
        elif ct.requires_fact and not has_facts:
            excluded.append({"slug": ct.slug, "reason": t("generation.missing_fact"), "kind": "insumos"})
        elif ct.slug == "antes_despues" and not {"antes", "despues"} <= tags:
            excluded.append({"slug": ct.slug, "reason": t("generation.missing_photos"), "kind": "insumos"})
        else:
            selected.append((ct, level, note))
    selected.sort(key=lambda item: (-rank.get(item[0].slug, (0, 0))[0], item[0].ord))
    selected = sorted(selected[: settings.creatives_max], key=lambda item: item[0].ord)
    return selected, excluded


def _new_piece(db: Session, proposal: Proposal, case: Case, *, kind: str, style: Style, resolved: ResolvedStyle, fmt: Format, content: dict[str, Any], why: str,
               creative: CreativeType | None = None, adaptation: str | None = None, missing: list[str] | None = None, illustrated: bool = False, run_id: int | None = None) -> Piece:
    piece = Piece(
        client_id=case.client_id, proposal_id=proposal.id, case_id=case.id, kind=kind, creative_slug=creative.slug if creative else None, format_slug=fmt.slug,
        account_id=proposal.account_id, flow=proposal.flow, style_id=style.id, style_slug=style.slug, style_version=style.version, strategy=proposal.strategy,
        intensity=resolved.intensity_target, effective_tags=piece_tags(style, fmt, proposal.strategy, proposal.flow, illustrated), applied_directives=resolved.trace(),
        adaptation=adaptation, why=why, content=content, missing_inputs=missing or [], render_status="no_aplica" if kind == "copy" else "pendiente",
    )
    db.add(piece)
    db.flush()
    db.add(PieceVersion(piece_id=piece.id, version=1, content=content, style_slug=style.slug, style_version=style.version, strategy=proposal.strategy,
                        intensity=piece.intensity, author_type="ia", action="generar", instruction="", ai_run_id=run_id))
    db.flush()
    return piece


def _illustration(db: Session, client_id: int, style: Style, fmt: Format, description: str, seed: int) -> dict[str, Any] | None:
    kind = ILLUSTRATION_KIND.get(fmt.template)
    if not kind:
        return None
    spec = build_image_spec(style.visual_guide, description, kind=kind, palette=style.palette, seed=seed, aspect_ratio="4:5")
    result = get_image_provider().generate(spec)
    key = get_storage().save(client_key(client_id, "generated", f"{uuid.uuid4().hex}.png"), result.data, result.mime)
    return {"generated": True, "key": key, "meta": {**result.meta, "prompt": spec.prompt, "negative_prompt": spec.negative_prompt}}


# ------------------------------------------------------------------ main entry points


def start_generation(db: Session, case: Case, user: User, variant_slugs: list[str] | None = None) -> Proposal:
    client = db.get(Client, case.client_id)
    if case.decision != "responder" or case.status not in ("listo_para_generar", "generado", "en_revision"):
        raise AppError(409, "conflict", t("pieces.errors.not_generable", status=case.status))
    if case.legal_required and case.legal_status != "liberada":
        raise AppError(409, "legal_pending", t("pieces.errors.legal_pending"))
    account = db.get(OwnedAccount, case.account_id) if case.account_id else None
    assert_registered_account(account, client.id)  # HR-02
    fmt = get_format(db, client.id, account.format_slug)
    veda = active_restriction(db, client.id)
    if veda and fmt.slug in (veda.blocked_formats or []):
        raise AppError(409, "veda", t("pieces.errors.veda_format"), details={"rule_id": "HR-04"})
    proposal = Proposal(client_id=client.id, case_id=case.id, account_id=account.id, format_slug=fmt.slug, flow=case.flow or "A", strategy=case.strategy or "contextualizar",
                        variant_styles=variant_slugs or [], status="generando", created_by_id=user.id)
    db.add(proposal)
    db.flush()
    transition(db, case, "generando", user, note=f"propuesta {proposal.id}")
    audit.record(db, action="proposal.start", entity_type="proposal", entity_id=proposal.id, client_id=client.id, user=user, note=case.code)
    return proposal


def generate_proposal(db: Session, proposal: Proposal, user: User | None = None) -> Proposal:
    case = db.get(Case, proposal.case_id)
    client = db.get(Client, case.client_id)
    settings = get_client_settings(client)
    account = db.get(OwnedAccount, proposal.account_id)
    fmt = get_format(db, client.id, proposal.format_slug)
    post = db.get(Post, case.post_id)
    topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))
    learning = learning_context(db, client.id, case.topic_slug, settings.learning_min_sample)
    proposal.learning_context = learning

    cited = [f for f in facts_for_case(db, case) if not is_expired(f) and f.document_id and any(f.id in (c.fact_ids or []) for c in case.interpretation.claims)] if case.interpretation else []
    pool = cited + [f for f in relevant_facts(db, client.id, post.text, topic.id if topic else None, limit=12) if f not in cited]
    facts = pool[:10]
    claims = [{"text": c.text, "verdict": c.verdict} for c in (case.interpretation.claims if case.interpretation else [])]
    kms = key_messages(db, client.id, topic.id if topic else None)
    complaint = case.message_type == "queja_ciudadana_legitima"

    if proposal.variant_styles:
        styles = [s for s in (active_style(db, client.id, slug) for slug in proposal.variant_styles) if s and style_allowed_for_format(s, fmt)]
    else:
        styles = variant_styles(db, client, fmt, case.style_slug)
    proposal.variant_styles = [s.slug for s in styles]
    pieces: list[Piece] = []

    # ---- copy variants (one per style)
    for i, style in enumerate(styles):
        resolved = resolve(db, client.id, style, topic=case.topic_slug, format_slug=fmt.slug, account_id=account.id, flow=proposal.flow)
        ctx = build_copy_context(client=client, resolved=resolved, strategy=proposal.strategy, flow=proposal.flow, topic=topic, post_text=post.text, facts=facts, key_msgs=kms,
                                 claims=claims, complaint=complaint, format_name=fmt.name, closing_phrase=(fmt.options or {}).get("closing_phrase"), account_handle=account.handle,
                                 variant=i, learning=learning)
        out, run = run_step(db, "generate_copy", ctx, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id, style_id=style.id, style_slug=style.slug,
                                                                style_version=style.version, applied_directives=resolved.trace()))
        segs = [s.model_dump() for s in out.segments]  # type: ignore[attr-defined]
        cited_facts = [f for f in facts if any(f.id in s["fact_ids"] for s in segs)]
        content = {"segments": segs, "legends": resolved.legend_texts, "sources": sources_for(cited_facts), "missing_data": out.missing_data}  # type: ignore[attr-defined]
        pieces.append(_new_piece(db, proposal, case, kind="copy", style=style, resolved=resolved, fmt=fmt, content=content, why=out.why, adaptation=out.adaptation, run_id=run.id))  # type: ignore[attr-defined]

    # ---- creatives (with the chosen style)
    main_style = styles[0]
    resolved = resolve(db, client.id, main_style, topic=case.topic_slug, format_slug=fmt.slug, account_id=account.id, flow=proposal.flow)
    photos = _photos(db, client.id, topic.id if topic else None)
    selected, excluded = select_creatives(db, client, proposal.flow, fmt, any(f.value is not None for f in facts), photos, learning)
    proposal.excluded_creatives = excluded
    ctx = build_copy_context(client=client, resolved=resolved, strategy=proposal.strategy, flow=proposal.flow, topic=topic, post_text=post.text, facts=facts, key_msgs=kms,
                             claims=claims, complaint=complaint, format_name=fmt.name, closing_phrase=(fmt.options or {}).get("closing_phrase"), account_handle=account.handle)
    ctx["format"] = {"slug": fmt.slug, "name": fmt.name}
    ctx["creatives"] = [{"slug": ct.slug, "name": ct.name, "level": level, "note": note, "required_slots": ct.required_slots, "template": ct.template, "requires_fact": ct.requires_fact} for ct, level, note in selected]
    ctx["images"] = [{"id": p.id, "title": p.title, "credit": p.credit, "tags": p.tags} for p in photos]
    if selected:
        out, run = run_step(db, "generate_creatives", ctx, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id, style_id=main_style.id,
                                                                     style_slug=main_style.slug, style_version=main_style.version, applied_directives=resolved.trace()))
        by_slug = {ct.slug: (ct, level, note) for ct, level, note in selected}
        facts_by_id = {f.id: f for f in facts}
        for n, draft in enumerate(out.creatives):  # type: ignore[attr-defined]
            if draft.creative_slug not in by_slug:
                continue  # the model may only propose creatives from the filtered catalog
            ct, level, note = by_slug[draft.creative_slug]
            slots = {s.name: {"text": s.text, "fact_ids": [i for i in s.fact_ids if i in facts_by_id]} for s in draft.slots}
            slides = [{"title": s.title, "text": s.text, "fact_ids": [i for i in s.fact_ids if i in facts_by_id]} for s in draft.slides]
            used = {i for s in slots.values() for i in s["fact_ids"]} | {i for s in slides for i in s["fact_ids"]}
            images: list[dict[str, Any]] = [{"approved_image_id": i} for i in draft.image_ids if any(p.id == i for p in photos)]
            if not images and not ct.text_only and fmt.template in ("clasico", "comparativa") and photos:
                images = [{"approved_image_id": p.id} for p in photos[: (2 if fmt.template == "comparativa" else 1)]]
            illustrated = False
            if not ct.text_only and not ct.requires_real_photo and fmt.template in ILLUSTRATION_KIND:
                gen = _illustration(db, client.id, main_style, fmt, f"{ct.name} sobre {topic.name if topic else 'el tema'}", seed=case.id * 100 + n)
                if gen:
                    images.append(gen)
                    illustrated = True
            content = {
                "template": ct.template, "slots": slots, "slides": slides, "images": images, "headline": (slots.get("titulo") or {}).get("text", ""),
                "sources": sources_for([facts_by_id[i] for i in sorted(used)]), "legends": resolved.legend_texts, "topic_name": topic.name if topic else "",
                "label": t("pieces.label_representative") if (fmt.options or {}).get("illustrated_figures") and not ct.text_only else None,
            }
            comparison = _comparison_from(draft)
            if comparison:
                content["comparison"] = comparison
            adaptation = draft.adaptation or (note if level == "partial" else None)
            pieces.append(_new_piece(db, proposal, case, kind="creative", style=main_style, resolved=resolved, fmt=fmt, content=content, why=draft.why, creative=ct,
                                     adaptation=adaptation, missing=draft.missing_inputs, illustrated=illustrated, run_id=run.id))

    for piece in pieces:
        validate_piece(db, piece)
    run_red_team(db, case, pieces, facts, user)
    for piece in pieces:
        refresh_piece_risk(db, case, piece)
    case.risk_score = max((p.risk_score or 0) for p in pieces) if pieces else case.risk_score
    proposal.status, proposal.finished_at = "listo", utcnow()
    transition(db, case, "generado", user, note=f"{len(pieces)} piezas")
    audit.record(db, action="proposal.done", entity_type="proposal", entity_id=proposal.id, client_id=client.id, user=user, after={"pieces": len(pieces), "excluded": len(excluded)})
    _render_all(db, pieces)
    return proposal


def _comparison_from(draft: Any) -> dict[str, Any] | None:
    """Comparisons (antes/después, comparativa) declare which facts are on each side so 9.1.4 can check them."""
    data = draft.model_dump() if hasattr(draft, "model_dump") else dict(draft)
    if data.get("comparison"):
        return {k: v for k, v in data["comparison"].items() if v is not None}
    slots = {s["name"]: s for s in data.get("slots", [])}
    if "lado_a" in slots and "lado_b" in slots:
        return {"left": slots["lado_a"]["fact_ids"], "right": slots["lado_b"]["fact_ids"], "mode": "comparativa"}
    return None


def _render_all(db: Session, pieces: list[Piece]) -> None:
    from app.render.renderer import render_piece

    for piece in pieces:
        if piece.kind == "creative":
            render_piece(db, piece)
    db.flush()


def piece_visible_text(piece: Piece) -> str:
    c = piece.content or {}
    if piece.kind == "copy":
        return " ".join(s.get("text", "") for s in c.get("segments") or [])
    parts = [s.get("text", "") for s in (c.get("slots") or {}).values()] + [f"{s.get('title', '')}. {s.get('text', '')}" for s in c.get("slides") or []]
    return " ".join(p for p in parts if p)


def run_red_team(db: Session, case: Case, pieces: list[Piece], facts: list[Fact], user: User | None) -> None:
    if not pieces:
        return
    post = db.get(Post, case.post_id)
    ctx = {
        "post_text": post.text,
        "pieces": [
            {"id": p.id, "kind": p.kind, "text": piece_visible_text(p), "satirical": "humor:satirico" in (p.effective_tags or []),
             "fact_ids": sorted({i for s in (p.content.get("segments") or []) for i in s.get("fact_ids", [])} | {i for s in (p.content.get("slots") or {}).values() for i in s.get("fact_ids", [])})}
            for p in pieces
        ],
        "facts": [fact_dict(f) for f in facts],
    }
    out, run = run_step(db, "red_team", ctx, StepMeta(client_id=case.client_id, user_id=user.id if user else None, case_id=case.id))
    by_id = {p.id: p for p in pieces}
    for p in pieces:
        for note in list(p.red_team_notes):
            db.delete(note)
        p.red_team_summary = {"alta": 0, "media": 0, "baja": 0}
    db.flush()
    for note in out.notes:  # type: ignore[attr-defined]
        pid_txt, _, target = note.target.partition("::")
        piece = by_id.get(int(pid_txt)) if pid_txt.isdigit() else None
        if piece is None:
            continue
        db.add(RedTeamNote(piece_id=piece.id, piece_version=piece.current_version, kind=note.kind, severity=note.severity, text=note.text, target=target, ai_run_id=run.id))
        summary = dict(piece.red_team_summary)
        summary[note.severity] = summary.get(note.severity, 0) + 1
        piece.red_team_summary = summary
    db.flush()


def refresh_piece_risk(db: Session, case: Case, piece: Piece) -> None:
    pending = sum(1 for f in piece.figures if f.status != "verificada")
    piece.risk_score, piece.risk_breakdown = case_risk(db, case, style_slug=piece.style_slug, unverified_figures=pending, red_team=piece.red_team_summary, piece_text=piece_visible_text(piece))
