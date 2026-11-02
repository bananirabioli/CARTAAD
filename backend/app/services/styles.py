"""Style lifecycle: versioning, activation (with legal for high risk), hard-rule checks, import/export, "Probar estilo"."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.runner import StepMeta, run_step
from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import check_text_against_hard_rules
from app.i18n import t
from app.models.core import Client, User
from app.models.styles import Style
from app.services import audit
from app.services.copy_context import build_copy_context, detect_topic, key_messages, relevant_facts, segments_text
from app.services.style_resolver import resolve
from app.validators.style_lint import lint

EDITABLE_FIELDS = (
    "name", "description", "tags", "free_tags", "intensity_min", "intensity_max", "voice", "guidelines", "preferred_vocab", "prohibited_vocab",
    "length", "emoji_usage", "caps_usage", "good_examples", "bad_examples", "visual_guide", "palette", "allowed_formats", "risk", "requires_legal",
)
VISUAL_FIELDS = ("visual_guide", "palette")
INTENT_TO_STRATEGY = {
    "desmentir": "desmentir", "contextualizar": "contextualizar", "informar": "contextualizar", "reencuadrar": "reencuadrar",
    "contrastar": "contrastar", "agradecer": "agradecer", "desescalar": "contextualizar", "movilizar": "amplificar",
}


def rules_for(style: Style) -> dict[str, Any]:
    from app.services.client_settings import rules_for as _rules_for

    return _rules_for(style) if style.client_id else {}


def client_rules(db: Session, client_id: int | None) -> dict[str, Any]:
    from app.models.core import Client
    from app.services.client_settings import get_client_settings, rules_dict

    client = db.get(Client, client_id) if client_id else None
    return rules_dict(get_client_settings(client)) if client else {}


def style_hard_rule_matches(data: dict[str, Any], rules: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Hard rules over the parts of a style that instruct generation (haz, visual guide, examples). `evita` lists are negations."""
    guidelines = data.get("guidelines") or {}
    texts = [data.get("visual_guide") or "", data.get("description") or "", *(guidelines.get("haz") or [])]
    return [m.as_dict() for m in check_text_against_hard_rules(*texts, rules=rules)]


def assert_style_ok(data: dict[str, Any], rules: dict[str, Any] | None = None) -> None:
    hits = style_hard_rule_matches(data, rules)
    if hits:
        raise AppError(422, "hard_rule", t("styles.errors.hard_rule", detail="; ".join(f"{h['rule_id']} «{h['snippet']}»" for h in hits)), details={"hard_rules": hits})
    if int(data.get("intensity_min", 1)) > int(data.get("intensity_max", 1)):
        raise AppError(422, "invalid_value", detail="intensity_min > intensity_max")


def latest_version(db: Session, client_id: int, slug: str) -> int:
    return db.scalar(select(func.max(Style.version)).where(Style.client_id == client_id, Style.slug == slug)) or 0


def new_version_from(db: Session, style: Style, user: User, changes: dict[str, Any], note: str = "") -> Style:
    data = {f: getattr(style, f) for f in EDITABLE_FIELDS}
    data.update(changes)
    assert_style_ok(data, rules_for(style))
    draft = Style(
        client_id=style.client_id, slug=style.slug, version=latest_version(db, style.client_id, style.slug) + 1, status="borrador",
        parent_id=style.id, created_by_id=user.id, change_note=note, **data,
    )
    if draft.risk == "alto":
        draft.requires_legal = True
    db.add(draft)
    db.flush()
    return draft


def update_draft(style: Style, changes: dict[str, Any]) -> None:
    if style.status not in ("borrador", "revision"):
        raise AppError(409, "conflict", t("styles.errors.not_editable"))
    data = {f: getattr(style, f) for f in EDITABLE_FIELDS}
    data.update(changes)
    assert_style_ok(data, rules_for(style))
    for k, v in changes.items():
        setattr(style, k, v)
    if style.risk == "alto":
        style.requires_legal = True
    style.legal_approved_by_id, style.legal_approved_at = None, None  # any change needs a new legal approval
    style.updated_at = utcnow()


def transition(db: Session, style: Style, target: str, user: User) -> None:
    allowed = {"borrador": {"revision", "activo", "archivado"}, "revision": {"borrador", "activo", "archivado"}, "activo": {"archivado"}, "archivado": {"borrador"}}
    if target not in allowed.get(style.status, set()):
        raise AppError(409, "conflict", t("styles.errors.bad_status", status=style.status))
    if target == "activo":
        assert_style_ok({f: getattr(style, f) for f in EDITABLE_FIELDS}, client_rules(db, style.client_id))
        if (style.requires_legal or style.risk == "alto") and not style.legal_approved_at:
            raise AppError(409, "legal_required", t("styles.errors.legal_required"))
        for other in db.scalars(select(Style).where(Style.client_id == style.client_id, Style.slug == style.slug, Style.status == "activo", Style.id != style.id)):
            other.status = "archivado"
            audit.record(db, action="style.archive", entity_type="style", entity_id=other.id, client_id=style.client_id, user=user, note=f"reemplazado por v{style.version}")
    style.status = target
    style.updated_at = utcnow()


def export_style(style: Style) -> dict[str, Any]:
    return {"slug": style.slug, "version": style.version, **{f: getattr(style, f) for f in EDITABLE_FIELDS}}


def import_style(db: Session, client_id: int, data: dict[str, Any], user: User) -> Style:
    slug = str(data.get("slug") or "").strip()
    if not slug:
        raise AppError(422, "invalid_value", detail="slug")
    fields = {f: data[f] for f in EDITABLE_FIELDS if f in data}
    fields.setdefault("name", slug)
    assert_style_ok(fields, client_rules(db, client_id))
    style = Style(client_id=client_id, slug=slug, version=latest_version(db, client_id, slug) + 1, status="borrador", created_by_id=user.id, change_note="Importado desde JSON", **fields)
    if style.risk == "alto":
        style.requires_legal = True
    db.add(style)
    db.flush()
    return style


def test_style(db: Session, client: Client, style: Style, user: User, text: str | None = None, flow: str | None = None) -> dict[str, Any]:
    """'Probar estilo': short sample of the style on a test text, with the same resolver and linter as generation."""
    sample = (text or "").strip() or t("styles.test.sample_post")
    topic = detect_topic(db, client.id, sample)
    intents = (style.tags or {}).get("intencion") or ["informar"]
    strategy = INTENT_TO_STRATEGY.get(intents[0], "contextualizar")
    flow = flow or ("B" if strategy in ("amplificar", "agradecer") else "A")
    resolved = resolve(db, client.id, style, topic=topic.slug if topic else None, flow=flow)
    facts = relevant_facts(db, client.id, sample, topic.id if topic else None, limit=2)
    context = build_copy_context(
        client=client, resolved=resolved, strategy=strategy, flow=flow, topic=topic, post_text=sample, facts=facts,
        key_msgs=key_messages(db, client.id, topic.id if topic else None), closing_phrase=None,
    )
    result, run = run_step(
        db, "generate_copy", context,
        StepMeta(client_id=client.id, user_id=user.id, style_id=style.id, style_slug=style.slug, style_version=style.version, applied_directives=resolved.trace()),
    )
    segments = [s.model_dump() for s in result.segments]  # type: ignore[attr-defined]
    full_text = segments_text(segments, resolved.legend_texts)
    status, findings = lint(full_text, resolved)
    return {
        "sample": sample,
        "topic": topic.name if topic else None,
        "strategy": strategy,
        "flow": flow,
        "segments": segments,
        "text": full_text,
        "why": result.why,  # type: ignore[attr-defined]
        "missing_data": result.missing_data,  # type: ignore[attr-defined]
        "lint_status": status,
        "findings": [f.as_dict() for f in findings],
        "resolved": resolved.summary(),
        "style_block": resolved.style_block(),
        "ai_run_id": run.id,
    }
