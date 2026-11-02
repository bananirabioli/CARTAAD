"""MVP generation: decide and generate in one step with a single generate_content call.

Produces copy pieces (one per style, same segments contract as generate_copy so validators, editor and approval work
unchanged), image pieces (prompt written by the model, sanitized for HR-11, drawn by the image provider) and an optional
video piece rendered later by the worker. The classic generate_copy / generate_creatives path stays for demo and tests.
"""

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.images import ImageSpec, get_image_provider
from app.ai.runner import StepMeta, run_step
from app.config import get_settings
from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import HardRuleViolation, generated_image_metadata, sanitize_image_prompt
from app.i18n import t
from app.models.cases import Case
from app.models.core import Client, Topic, User
from app.models.generation import Piece, PieceVersion, Proposal
from app.models.monitoring import OwnedAccount, Post
from app.models.styles import Style
from app.services import audit
from app.services.cases import CLOSING, decide, facts_for_case, reopen, transition
from app.services.catalog import active_style, get_format, style_allowed_for_format
from app.services.client_settings import get_client_settings
from app.services.copy_context import fact_dict, key_messages, relevant_facts
from app.services.facts import is_expired
from app.services.generation import _new_piece, refresh_piece_risk, run_red_team, sources_for, variant_styles
from app.services.style_resolver import resolve
from app.storage import client_key, get_storage
from app.validators.runner import validate_piece

NETWORK_FORMAT = {"facebook": "Publicación de Facebook", "x": "Post de X", "instagram": "Post de Instagram", "tiktok": "Video de TikTok",
                  "youtube": "Short de YouTube", "whatsapp": "Mensaje para WhatsApp"}
_DIGITS = re.compile(r"\d+")


def _main_account(db: Session, client: Client) -> OwnedAccount:
    from app.seed.production import ensure_main_account

    account = db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == client.id, OwnedAccount.account_type == "propia",
                                                  OwnedAccount.registered.is_(True), OwnedAccount.verified.is_(True), OwnedAccount.active.is_(True)))
    return account or ensure_main_account(db, client)


def start_content_generation(db: Session, case: Case, user: User, *, strategy: str | None, style_slug: str | None, variant_slugs: list[str] | None,
                             network: str, image_count: int, video: bool, instructions: str) -> Proposal:
    client = db.get(Client, case.client_id)
    if case.status in CLOSING:
        reopen(db, case, user, "generar contenido")
    if case.flow is None:  # neutral posts are auto-monitored; generating means the team wants to answer or amplify
        case.flow = "A" if case.stance == "en_contra" or case.message_type == "queja_ciudadana_legitima" else "B"
    if case.status == "interpretado":
        decide(db, case, user, decision="responder", strategy=strategy, style_slug=style_slug, account_id=_main_account(db, client).id)
    elif strategy or style_slug:
        case.strategy = strategy or case.strategy
        case.style_slug = style_slug or case.style_slug
    if case.legal_required and case.legal_status != "liberada":
        raise AppError(409, "legal_pending", t("pieces.errors.legal_pending"))
    if case.status not in ("listo_para_generar", "generado", "en_revision"):
        raise AppError(409, "conflict", t("pieces.errors.not_generable", status=case.status))
    account = db.get(OwnedAccount, case.account_id) if case.account_id else _main_account(db, client)
    fmt = get_format(db, client.id, account.format_slug)
    proposal = Proposal(
        client_id=client.id, case_id=case.id, account_id=account.id, format_slug=fmt.slug, flow=case.flow or "A", strategy=case.strategy or "contextualizar",
        variant_styles=variant_slugs or [], status="generando", created_by_id=user.id,
        options={"mode": "content", "network": network, "image_count": image_count, "video": video, "instructions": instructions.strip(), "style_slug": case.style_slug},
    )
    db.add(proposal)
    db.flush()
    transition(db, case, "generando", user, note=f"propuesta {proposal.id}")
    audit.record(db, action="proposal.start", entity_type="proposal", entity_id=proposal.id, client_id=client.id, user=user, note=f"{case.code} · contenido", after=proposal.options)
    return proposal


def _media_piece(db: Session, proposal: Proposal, case: Case, *, kind: str, style: Style, fmt_slug: str, content: dict[str, Any], why: str, run_id: int | None) -> Piece:
    piece = Piece(
        client_id=case.client_id, proposal_id=proposal.id, case_id=case.id, kind=kind, format_slug=fmt_slug, account_id=proposal.account_id, flow=proposal.flow,
        style_id=style.id, style_slug=style.slug, style_version=style.version, strategy=proposal.strategy, effective_tags=[f"estilo:{style.slug}", f"tipo:{kind}", "ilustracion"],
        why=why, content=content, render_status="pendiente", validation=[], validation_status="ok",
    )
    db.add(piece)
    db.flush()
    db.add(PieceVersion(piece_id=piece.id, version=1, content=content, style_slug=style.slug, style_version=style.version, strategy=proposal.strategy,
                        intensity=piece.intensity, author_type="ia", action="generar", instruction="", ai_run_id=run_id))
    db.flush()
    return piece


def safe_visual_prompt(prompt: str, negative: str, fallback: str) -> tuple[str, str]:
    """HR-11: image/video models never draw text, figures, logos or real faces. Digits go; a forbidden request falls back."""
    clean = re.sub(r"\s+", " ", _DIGITS.sub("", prompt)).strip()
    try:
        return sanitize_image_prompt(clean, negative)
    except HardRuleViolation:
        return sanitize_image_prompt(re.sub(r"\s+", " ", _DIGITS.sub("", fallback)).strip() or "Original illustration, soft shapes, warm light", negative)


def generate_content_proposal(db: Session, proposal: Proposal, user: User | None = None) -> Proposal:
    s = get_settings()
    opts = proposal.options or {}
    case = db.get(Case, proposal.case_id)
    client = db.get(Client, case.client_id)
    settings = get_client_settings(client)
    account = db.get(OwnedAccount, proposal.account_id)
    fmt = get_format(db, client.id, proposal.format_slug)
    post = db.get(Post, case.post_id)
    topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))

    cited = [f for f in facts_for_case(db, case) if not is_expired(f) and f.document_id] if case.interpretation else []
    pool = cited + [f for f in relevant_facts(db, client.id, post.text, topic.id if topic else None, limit=12) if f not in cited]
    facts = pool[:10]
    claims = [{"text": c.text, "verdict": c.verdict} for c in (case.interpretation.claims if case.interpretation else [])]

    if proposal.variant_styles:
        styles = [st for st in (active_style(db, client.id, slug) for slug in proposal.variant_styles) if st and style_allowed_for_format(st, fmt)]
    else:
        styles = variant_styles(db, client, fmt, case.style_slug)
    if not styles:
        raise AppError(409, "conflict", "No hay estilos activos para este formato: revisa Catálogos → Estilos.")
    proposal.variant_styles = [st.slug for st in styles]
    main = styles[0]
    resolved = resolve(db, client.id, main, topic=case.topic_slug, format_slug=fmt.slug, account_id=account.id, flow=proposal.flow)
    image_count, want_video = int(opts.get("image_count", 1)), bool(opts.get("video"))
    ctx = {
        "client_name": client.name, "client_context": settings.context, "client_tone": client.default_tone, "style_block": resolved.style_block(),
        "network": opts.get("network", "facebook"), "format_name": NETWORK_FORMAT.get(opts.get("network", ""), fmt.name), "strategy": proposal.strategy,
        "stance": case.stance, "message_type": case.message_type, "topic_name": topic.name if topic else "sin tema", "post_text": post.text,
        "summary": case.interpretation.summary if case.interpretation else "", "claims": claims, "instructions": opts.get("instructions", ""),
        "styles": [{"slug": st.slug, "name": st.name, "description": st.description, "visual_guide": st.visual_guide} for st in styles],
        "key_messages": key_messages(db, client.id, topic.id if topic else None), "facts": [fact_dict(f) for f in facts],
        "max_images": max(image_count, 1), "want_video": want_video, "video_seconds": s.video_max_seconds,
    }
    out, run = run_step(db, "generate_content", ctx, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id, style_id=main.id,
                                                              style_slug=main.slug, style_version=main.version, applied_directives=resolved.trace()))
    pieces: list[Piece] = []
    facts_by_id = {f.id: f for f in facts}
    by_slug = {st.slug: st for st in styles}

    # ---- copies: one per style, matched by slug (falls back to order)
    for i, variant in enumerate(out.copies[: len(styles)]):  # type: ignore[attr-defined]
        style = by_slug.get(variant.style) or styles[min(i, len(styles) - 1)]
        style_resolved = resolve(db, client.id, style, topic=case.topic_slug, format_slug=fmt.slug, account_id=account.id, flow=proposal.flow)
        segs = [{**sg.model_dump(), "fact_ids": [x for x in sg.fact_ids if x in facts_by_id]} for sg in variant.segments]
        used = sorted({x for sg in segs for x in sg["fact_ids"]})
        content = {"segments": segs, "legends": style_resolved.legend_texts, "sources": sources_for([facts_by_id[x] for x in used]),
                   "missing_data": out.missing_data, "hashtags": variant.hashtags, "cta": variant.cta, "network": opts.get("network")}  # type: ignore[attr-defined]
        pieces.append(_new_piece(db, proposal, case, kind="copy", style=style, resolved=style_resolved, fmt=fmt, content=content, why=variant.why, run_id=run.id))

    # ---- images: the model writes the prompt; code sanitizes it and the provider draws it
    media: list[Piece] = []
    if image_count:
        for n, ip in enumerate(out.image_prompts[:image_count]):  # type: ignore[attr-defined]
            prompt, negative = safe_visual_prompt(ip.prompt, ip.negative_prompt, f"{main.visual_guide}. Original illustration about {ip.concept}")
            content = {"concept": ip.concept, "prompt": prompt, "negative_prompt": negative, "aspect_ratio": ip.aspect_ratio, "headline": ip.headline}
            piece = _media_piece(db, proposal, case, kind="image", style=main, fmt_slug=fmt.slug, content=content, why=ip.concept, run_id=run.id)
            try:
                result = get_image_provider().generate(ImageSpec(prompt=prompt, negative_prompt=negative, aspect_ratio=ip.aspect_ratio, seed=case.id * 100 + n, palette=main.palette))
                ext = "jpg" if "jpeg" in result.mime else "png"
                key = get_storage().save(client_key(client.id, "generated", f"{uuid.uuid4().hex}.{ext}"), result.data, result.mime)
                piece.content = {**content, "meta": result.meta}
                piece.renders, piece.render_status = [key], "listo"
            except Exception as exc:  # noqa: BLE001 - keep the prompt usable even if the image model fails
                piece.render_status, piece.render_error = "error", str(exc)[:500]
            media.append(piece)

    # ---- video: planned now, rendered by the worker (it takes minutes)
    if want_video and out.video:  # type: ignore[attr-defined]
        v = out.video  # type: ignore[attr-defined]
        prompt, negative = safe_visual_prompt(v.prompt, "", f"{main.visual_guide}. Short cinematic shot about {v.concept}")
        content = {"concept": v.concept, "scenes": [sc.model_dump() for sc in v.scenes], "prompt": prompt, "negative_prompt": negative, "aspect_ratio": v.aspect_ratio,
                   "voiceover": v.voiceover_full, "on_screen_text": v.on_screen_text, "seconds": s.video_max_seconds,
                   "meta": generated_image_metadata(provider=s.video_provider, model=s.openrouter_model_video if s.video_provider == "openrouter" else None)}
        piece = _media_piece(db, proposal, case, kind="video", style=main, fmt_slug=fmt.slug, content=content, why=v.concept, run_id=run.id)
        if s.video_provider == "none":
            piece.render_status, piece.render_error = "no_aplica", "Generación de video desactivada (VIDEO_PROVIDER=none): usa el prompt y el guion."
        media.append(piece)

    for piece in pieces:
        validate_piece(db, piece)
    run_red_team(db, case, pieces, facts, user)
    for piece in pieces:
        refresh_piece_risk(db, case, piece)
    for piece in media:
        piece.status = "generado"
    case.risk_score = max((p.risk_score or 0) for p in pieces) if pieces else case.risk_score
    pieces += media
    proposal.status, proposal.finished_at = "listo", utcnow()
    transition(db, case, "generado", user, note=f"{len(pieces)} piezas")
    audit.record(db, action="proposal.done", entity_type="proposal", entity_id=proposal.id, client_id=client.id, user=user, after={"pieces": len(pieces)})
    db.flush()
    return proposal


def video_pieces_to_render(proposal: Proposal) -> list[int]:
    return [p.id for p in proposal.pieces if p.kind == "video" and p.render_status == "pendiente"]


def render_video(db: Session, piece: Piece) -> str | None:
    """Blocking: submit, poll and download. Runs in the worker."""
    from app.ai.openrouter import generate_video

    c = piece.content or {}
    try:
        data, meta = generate_video(c.get("prompt", ""), aspect_ratio=c.get("aspect_ratio", "9:16"), duration=c.get("seconds"))
    except Exception as exc:  # noqa: BLE001
        piece.render_status, piece.render_error = "error", str(exc)[:500]
        return None
    key = get_storage().save(client_key(piece.client_id, "videos", f"{piece.id}-{uuid.uuid4().hex[:8]}.mp4"), data, "video/mp4")
    piece.content = {**c, "meta": {**(c.get("meta") or {}), **meta}}
    piece.renders, piece.render_status, piece.render_error = [key], "listo", ""
    return key
