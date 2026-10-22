"""Case lifecycle (section 5): capture → classify → interpret → human decision → [legal] → generation → … → rating.

Every transition is written to AuditLog. The LLM proposes (classification, interpretation, strategy); code computes the
alert level and risk score; people decide, verify and approve.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import cosine
from app.ai.runner import StepMeta, run_step
from app.api.deps import next_code
from app.db import utcnow
from app.errors import AppError
from app.guardrails.hard_rules import COMPLAINT_ALLOWED_STRATEGIES, assert_complaint_routing, assert_registered_account, requires_legal_review
from app.i18n import t
from app.models.cases import Case, Claim, Classification, Interpretation
from app.models.core import Client, Topic, User
from app.models.kb import Competence, Fact, GovLevel
from app.models.monitoring import OwnedAccount, Post
from app.services import audit
from app.services.actors import client_actors, mentioned_actors
from app.services.catalog import active_style, effective_style, get_format, style_allowed_for_format
from app.services.client_settings import get_client_settings
from app.services.copy_context import fact_dict, relevant_facts
from app.services.learning import learning_context, recommend_from
from app.services.risk import compute_risk
from app.services.veda import active_restriction

TRANSITIONS: dict[str, set[str]] = {
    "capturado": {"clasificado"},
    "clasificado": {"interpretado"},
    "interpretado": {"revision_legal", "listo_para_generar", "monitoreando", "ignorado", "canalizado", "descartado"},
    "revision_legal": {"listo_para_generar", "descartado"},
    "listo_para_generar": {"generando", "generado", "descartado", "interpretado"},
    "generando": {"generado", "listo_para_generar"},
    "generado": {"en_revision", "generando", "descartado"},
    "en_revision": {"aprobado", "generado", "generando", "descartado"},
    "aprobado": {"programado", "en_revision", "generando", "publicado"},
    "programado": {"publicado", "aprobado"},
    "publicado": {"medido"},
    "medido": {"calificado", "medido"},
    "calificado": set(),
    "monitoreando": {"interpretado"},
    "ignorado": {"interpretado"},
    "canalizado": {"interpretado"},
    "descartado": {"interpretado"},
}
CLOSING = {"monitoreando", "ignorado", "canalizado", "descartado"}


def transition(db: Session, case: Case, target: str, user: User | None, note: str = "") -> None:
    if target == case.status:
        return
    if target not in TRANSITIONS.get(case.status, set()):
        raise AppError(409, "conflict", t("cases.bad_transition", **{"from": case.status, "to": target}))
    before = case.status
    case.status = target
    case.updated_at = utcnow()
    audit.record(db, action="case.transition", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, before={"status": before}, after={"status": target}, note=note)


def flow_for(stance: str, message_type: str) -> str | None:
    if message_type == "queja_ciudadana_legitima" or stance == "en_contra":
        return "A"
    if stance == "a_favor":
        return "B"
    return None


# ------------------------------------------------------------------ pipeline steps


def create_case(db: Session, post: Post, user: User | None = None) -> Case:
    case = Case(client_id=post.client_id, post_id=post.id, code=next_code(db, post.client_id, "case", "C", 4), status="capturado", alert_level=post.alert_level)
    db.add(case)
    db.flush()
    audit.record(db, action="case.create", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, after={"status": "capturado", "post_id": post.id}, note=case.code)
    return case


def classify_case(db: Session, case: Case, post: Post, user: User | None = None) -> Classification:
    client = db.get(Client, case.client_id)
    topics = [{"slug": tp.slug, "name": tp.name, "keywords": tp.keywords} for tp in db.scalars(select(Topic).where(Topic.client_id == client.id, Topic.active.is_(True)))]
    context = {
        "client_name": client.name, "client_type": client.client_type, "topics": topics,
        "post": {"text": post.text, "image_text": post.image_text, "network": post.network, "source_name": post.source.name if post.source else None, "source_type": post.source.source_type if post.source else None},
        "alert": {"level": post.alert_level, "ratio": post.alert_ratio, "velocity": post.velocity},
        "comments_sample": [c.text for c in post.comments][:8],
    }
    out, run = run_step(db, "classify", context, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id))
    data = out.model_dump()
    if data["topic"] not in {tp["slug"] for tp in topics}:
        data["topic"] = "otro"
    if data["message_type"] == "queja_ciudadana_legitima":
        data["canalizar_a_atencion"] = True  # HR-05: routing flag is enforced in code
    cls = db.scalar(select(Classification).where(Classification.post_id == post.id))
    if cls is None:
        cls = Classification(post_id=post.id, client_id=post.client_id, stance="neutral", topic_slug="otro", message_type="opinion", recommendation="monitorear")
        db.add(cls)
    cls.stance, cls.topic_slug, cls.message_type = data["stance"], data["topic"], data["message_type"]
    cls.recommendation, cls.confidence, cls.explanation = data["recommendation"], data["confidence"], data["explanation"]
    cls.canalizar_a_atencion = data["canalizar_a_atencion"]
    cls.alert_level, cls.alert_ratio, cls.velocity = post.alert_level, post.alert_ratio, post.velocity
    cls.ai_run_id = run.id
    db.flush()
    sync_case_from_classification(case, cls)
    transition(db, case, "clasificado", user, note=f"{cls.stance} · {cls.message_type} · {cls.topic_slug}")
    return cls


def sync_case_from_classification(case: Case, cls: Classification) -> None:
    case.topic_slug, case.message_type, case.stance = cls.topic_slug, cls.message_type, cls.stance
    case.alert_level = cls.alert_level
    case.flow = flow_for(cls.stance, cls.message_type)
    case.canalizar_a_atencion = cls.canalizar_a_atencion
    case.legal_required = requires_legal_review(False, False, False, message_type=cls.message_type)
    if case.legal_required and case.legal_status == "no_requerida":
        case.legal_status = "pendiente"
    if not case.legal_required and case.legal_status == "pendiente":
        case.legal_status = "no_requerida"


def find_repeated(db: Session, post: Post, topic_slug: str | None, window_hours: int, threshold: float, limit: int = 6) -> list[dict[str, Any]]:
    """Same topic and semantically similar posts from *other* pages within the time window."""
    if not post.embedding:
        return []
    since, until = post.published_at - timedelta(hours=window_hours), post.published_at + timedelta(hours=window_hours)
    stmt = select(Post).where(Post.client_id == post.client_id, Post.id != post.id, Post.is_history.is_(False), Post.published_at.between(since, until))
    out = []
    for other in db.scalars(stmt):
        if other.source_id is not None and other.source_id == post.source_id:
            continue
        other_cls = db.scalar(select(Classification).where(Classification.post_id == other.id))
        if topic_slug and other_cls and other_cls.topic_slug != topic_slug:
            continue
        score = cosine(post.embedding, other.embedding)
        if score >= threshold:
            out.append({"post_id": other.id, "source": other.source.name if other.source else "captura manual", "text": other.text[:200], "similarity": round(score, 2), "published_at": other.published_at.isoformat()})
    out.sort(key=lambda r: r["similarity"], reverse=True)
    return out[:limit]


def interpret_case(db: Session, case: Case, user: User | None = None) -> Interpretation:
    post = db.get(Post, case.post_id)
    cls = db.scalar(select(Classification).where(Classification.post_id == post.id))
    client = db.get(Client, case.client_id)
    settings = get_client_settings(client)
    topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))
    facts = relevant_facts(db, client.id, post.text, topic.id if topic else None, limit=10, usable_only=False)
    if topic:
        same_topic = [f for f in facts if f.topic_id == topic.id]
        facts = same_topic + [f for f in facts if f.topic_id != topic.id][: max(0, 10 - len(same_topic))]
    competences = []
    if topic:
        for comp in db.scalars(select(Competence).where(Competence.client_id == client.id, Competence.topic_id == topic.id)):
            level = db.get(GovLevel, comp.gov_level_id)
            competences.append({"level": level.name if level else "", "description": comp.description})
    context = {
        "client_name": client.name,
        "post": {"text": post.text, "network": post.network, "source_name": post.source.name if post.source else None},
        "classification": {"stance": cls.stance, "message_type": cls.message_type, "topic": cls.topic_slug},
        "facts": [fact_dict(f) | {"topic": topic.slug if topic and f.topic_id == topic.id else None} for f in facts],
        "chunks": [],
        "competences": competences,
        "comments": [c.text for c in post.comments],
    }
    out, run = run_step(db, "interpret", context, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id))
    data = out.model_dump()
    valid_ids = {f.id for f in facts}
    interp = case.interpretation or Interpretation(case_id=case.id)
    if case.interpretation is None:
        db.add(interp)
    interp.summary, interp.narrative = data["summary"], data["narrative"]
    interp.missing_context, interp.comments_summary = data["missing_context"], data["comments_summary"]
    interp.repeated_in = find_repeated(db, post, cls.topic_slug, settings.coordinated_window_hours, settings.repeated_similarity)
    interp.fact_ids_considered = sorted(valid_ids)
    interp.ai_run_id = run.id
    db.flush()
    for claim in list(interp.claims):
        db.delete(claim)
    db.flush()
    for c in data["claims"]:
        ids = [i for i in c.get("fact_ids", []) if i in valid_ids]  # never trust ids outside the context
        db.add(Claim(interpretation_id=interp.id, text=c["text"], verdict=c["verdict"], fact_ids=ids, explanation=c["explanation"], missing_data=c.get("missing_data")))
    db.flush()
    db.refresh(interp)
    if case.status == "clasificado":
        transition(db, case, "interpretado", user, note=f"{len(data['claims'])} afirmaciones")
    return interp


def strategy_candidates(settings, stance: str | None, message_type: str | None) -> list[str]:  # noqa: ANN001
    mapping = settings.strategy_mapping
    if stance == "a_favor":
        cands = mapping.get("a_favor", ["amplificar", "agradecer"])
    else:
        cands = mapping.get(message_type or "opinion", ["contextualizar"])
    if message_type == "queja_ciudadana_legitima":
        cands = [c for c in cands if c in COMPLAINT_ALLOWED_STRATEGIES] or ["contextualizar"]
    return cands


def suggest_strategy(db: Session, case: Case, user: User | None = None) -> None:
    client = db.get(Client, case.client_id)
    settings = get_client_settings(client)
    if case.flow is None:
        case.strategy_suggested, case.strategy_justification, case.strategy_alternatives = None, "", []
        return
    learning = learning_context(db, client.id, case.topic_slug, settings.learning_min_sample)
    case.learning_context = learning
    claims = [{"text": c.text, "verdict": c.verdict} for c in (case.interpretation.claims if case.interpretation else [])]
    topic = db.scalar(select(Topic).where(Topic.client_id == client.id, Topic.slug == case.topic_slug))
    context = {
        "client_name": client.name, "topic_name": topic.name if topic else case.topic_slug, "flow": case.flow,
        "classification": {"stance": case.stance, "message_type": case.message_type},
        "candidates": strategy_candidates(settings, case.stance, case.message_type), "claims": claims, "learning": learning,
    }
    out, _ = run_step(db, "recommend_strategy", context, StepMeta(client_id=client.id, user_id=user.id if user else None, case_id=case.id))
    data = out.model_dump()
    strategy = data["strategy"] if data["strategy"] in context["candidates"] else context["candidates"][0]
    case.strategy_suggested, case.strategy_justification, case.strategy_alternatives = strategy, data["justification"], data["alternatives"]
    style_reco = recommend_from(learning, "styles")
    if case.message_type == "queja_ciudadana_legitima":
        style_reco = {**style_reco, "value": settings.complaint_style, "reason": t("hard_rules.HR-05.description")}
    case.recommended_style = style_reco


def case_risk(db: Session, case: Case, *, style_slug: str | None = None, unverified_figures: int | None = None, red_team: dict[str, int] | None = None, piece_text: str | None = None) -> tuple[int, list[dict[str, Any]]]:
    client = db.get(Client, case.client_id)
    settings = get_client_settings(client)
    style = active_style(db, client.id, style_slug or case.style_slug or (case.recommended_style or {}).get("value"))
    post = db.get(Post, case.post_id)
    actors = [a.name for a in mentioned_actors(client_actors(db, client.id), piece_text if piece_text is not None else post.text, include_own=False)]
    if unverified_figures is None:
        unverified_figures = sum(1 for c in (case.interpretation.claims if case.interpretation else []) if c.verdict == "no_verificable")
    return compute_risk(
        settings, alert_level=case.alert_level, message_type=case.message_type, stance=case.stance, style_risk=style.risk if style else None,
        unverified_figures=unverified_figures, actors_named=actors, veda_active=active_restriction(db, client.id) is not None, red_team=red_team,
    )


def refresh_risk(db: Session, case: Case) -> None:
    case.risk_score, case.risk_breakdown = case_risk(db, case)


def process_new_post(db: Session, post: Post, user: User | None = None) -> Case:
    case = create_case(db, post, user)
    classify_case(db, case, post, user)
    interpret_case(db, case, user)
    suggest_strategy(db, case, user)
    refresh_risk(db, case)
    if case.flow is None:  # neutral → monitorear by default (section 4)
        case.decision, case.decision_reason, case.decided_at = "monitorear", t("cases.auto_monitor"), utcnow()
        transition(db, case, "monitoreando", user, note=t("cases.auto_monitor"))
    return case


def reprocess(db: Session, case: Case, user: User | None) -> None:
    """After a human edits the classification: re-run interpretation, strategy and risk without touching the decision."""
    interpret_case(db, case, user)
    suggest_strategy(db, case, user)
    refresh_risk(db, case)


# ------------------------------------------------------------------ human decision & legal


def decide(
    db: Session,
    case: Case,
    user: User,
    *,
    decision: str,
    reason: str = "",
    strategy: str | None = None,
    style_slug: str | None = None,
    account_id: int | None = None,
) -> Case:
    client = db.get(Client, case.client_id)
    if case.status not in ("interpretado",):
        raise AppError(409, "conflict", t("cases.bad_transition", **{"from": case.status, "to": decision}))
    if decision in ("monitorear", "ignorar", "canalizar") and len(reason.strip()) < 3:
        raise AppError(422, "invalid_value", t("cases.reason_required"))
    before = audit.snapshot(case, ["decision", "strategy", "style_slug", "account_id", "status"])
    case.decision, case.decision_reason, case.decided_by_id, case.decided_at = decision, reason.strip(), user.id, utcnow()
    if decision == "responder":
        strategy = strategy or case.strategy_suggested or "contextualizar"
        assert_complaint_routing(case.message_type, case.canalizar_a_atencion, strategy)  # HR-05
        account = db.get(OwnedAccount, account_id) if account_id else None
        if account is None or account.client_id != client.id:
            raise AppError(422, "invalid_value", t("cases.no_account"))
        assert_registered_account(account, client.id)  # HR-02
        fmt = get_format(db, client.id, account.format_slug)
        if case.message_type == "queja_ciudadana_legitima" and not style_slug:
            style_slug = get_client_settings(client).complaint_style
        choice = effective_style(client, fmt, account.default_style_slug, style_slug)
        style = active_style(db, client.id, choice.slug)
        if style is None or (fmt and not style_allowed_for_format(style, fmt)):
            if style_slug:
                raise AppError(422, "invalid_value", t("cases.style_not_allowed", style=choice.slug))
            choice = effective_style(client, fmt, None, None)
            style = active_style(db, client.id, choice.slug)
        case.strategy, case.account_id = strategy, account.id
        case.style_slug, case.style_choice = (style.slug if style else choice.slug), {"slug": choice.slug, "source": choice.source, "reason": choice.reason}
        refresh_risk(db, case)
        target = "revision_legal" if case.legal_required and case.legal_status != "liberada" else "listo_para_generar"
        transition(db, case, target, user, note=f"responder · {strategy} · {case.style_slug}")
    else:
        target = {"monitorear": "monitoreando", "ignorar": "ignorado", "canalizar": "canalizado"}[decision]
        if decision == "canalizar":
            case.canalizar_a_atencion = True
        case.closed_reason = reason.strip()
        transition(db, case, target, user, note=reason.strip())
    audit.record(db, action="case.decide", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, before=before, after=audit.snapshot(case, ["decision", "strategy", "style_slug", "account_id", "status"]))
    return case


def legal_review(db: Session, case: Case, user: User, *, action: str, note: str) -> Case:
    if action not in ("liberar", "bloquear"):
        raise AppError(422, "invalid_value", detail=action)
    if len(note.strip()) < 3:
        raise AppError(422, "invalid_value", t("cases.reason_required"))
    case.legal_status = "liberada" if action == "liberar" else "bloqueada"
    case.legal_note, case.legal_by_id, case.legal_at = note.strip(), user.id, utcnow()
    audit.record(db, action=f"case.legal_{action}", entity_type="case", entity_id=case.id, client_id=case.client_id, user=user, after={"legal_status": case.legal_status}, note=note)
    if case.status == "revision_legal":
        if action == "liberar":
            transition(db, case, "listo_para_generar", user, note="legal liberó")
        else:
            case.closed_reason = f"Bloqueado por legal: {note.strip()}"
            transition(db, case, "descartado", user, note=case.closed_reason)
    return case


def close_case(db: Session, case: Case, user: User, reason: str) -> Case:
    if len(reason.strip()) < 3:
        raise AppError(422, "invalid_value", t("cases.reason_required"))
    case.closed_reason = reason.strip()
    transition(db, case, "descartado", user, note=reason.strip())
    return case


def reopen(db: Session, case: Case, user: User, reason: str) -> Case:
    if case.status not in CLOSING:
        raise AppError(409, "conflict", t("cases.bad_transition", **{"from": case.status, "to": "interpretado"}))
    case.decision, case.closed_reason = None, ""
    transition(db, case, "interpretado", user, note=f"reabierto: {reason}")
    return case


def facts_for_case(db: Session, case: Case) -> list[Fact]:
    ids: set[int] = set()
    if case.interpretation:
        ids |= set(case.interpretation.fact_ids_considered or [])
        for c in case.interpretation.claims:
            ids |= set(c.fact_ids or [])
    return list(db.scalars(select(Fact).where(Fact.client_id == case.client_id, Fact.id.in_(ids)))) if ids else []
