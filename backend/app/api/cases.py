"""Casos (secciones 4 y 5): lista, detalle, clasificación editable, decisión humana, legal y tablero."""

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select

from app.api.deps import Ctx, get_ctx, owned, require
from app.db import utcnow
from app.errors import AppError
from app.models.cases import Case, Classification
from app.models.core import AuditLog, User
from app.models.monitoring import OwnedAccount, Post
from app.schemas.cases import (
    AccountOption,
    AssignIn,
    CaseDetail,
    CaseListItem,
    ClassificationOut,
    ClassificationPatch,
    DashboardOut,
    DecideIn,
    InterpretationOut,
    LegalIn,
    ReasonIn,
)
from app.schemas.common import Page
from app.schemas.monitoring import PostDetail
from app.services import audit
from app.services import cases as case_svc
from app.services.catalog import active_style, effective_style, format_style_slugs, get_format, style_allowed_for_format
from app.services.facts import fact_out

router = APIRouter(tags=["cases"])


def _pieces_count(ctx: Ctx, case: Case) -> int:
    try:
        from app.models.generation import Piece
    except ImportError:  # pragma: no cover - before M5
        return 0
    return ctx.db.scalar(select(func.count()).where(Piece.case_id == case.id, Piece.status != "descartado")) or 0


def _list_item(ctx: Ctx, case: Case, model: type[CaseListItem] = CaseListItem) -> CaseListItem:
    post = ctx.db.get(Post, case.post_id)
    cls = ctx.db.scalar(select(Classification).where(Classification.post_id == case.post_id))
    assigned = ctx.db.get(User, case.assigned_to_id) if case.assigned_to_id else None
    return model.model_validate(case).model_copy(
        update={
            "post_text": post.text[:280], "source_name": post.source.name if post.source else None, "network": post.network,
            "alert_ratio": post.alert_ratio, "recommendation": cls.recommendation if cls else None,
            "assigned_to_name": assigned.name if assigned else None, "pieces_count": _pieces_count(ctx, case),
        }
    )


def _account_options(ctx: Ctx) -> list[AccountOption]:
    out = []
    for acc in ctx.db.scalars(select(OwnedAccount).where(OwnedAccount.client_id == ctx.client_id, OwnedAccount.active.is_(True), OwnedAccount.registered.is_(True), OwnedAccount.verified.is_(True))):
        fmt = get_format(ctx.db, ctx.client_id, acc.format_slug)
        if not fmt:
            continue
        allowed = [s for s in format_style_slugs(fmt) if (st := active_style(ctx.db, ctx.client_id, s)) and style_allowed_for_format(st, fmt)]
        choice = effective_style(ctx.client, fmt, acc.default_style_slug, None)
        out.append(
            AccountOption(
                id=acc.id, handle=acc.handle, display_name=acc.display_name, account_type=acc.account_type, network=acc.network, format_slug=fmt.slug,
                format_name=f"{fmt.code} · {fmt.name}", allowed_styles=allowed, default_style=choice.slug, default_source=choice.source,
            )
        )
    return out


def _detail(ctx: Ctx, case: Case) -> CaseDetail:
    from app.api.monitoring import _post_out
    from app.services.cases import strategy_candidates

    base = _list_item(ctx, case)
    post = ctx.db.get(Post, case.post_id)
    cls = ctx.db.scalar(select(Classification).where(Classification.post_id == case.post_id))
    decided_by = ctx.db.get(User, case.decided_by_id) if case.decided_by_id else None
    timeline = [
        {"at": a.created_at.isoformat(), "who": a.user_label, "action": a.action, "note": a.note, "after": a.after}
        for a in ctx.db.scalars(select(AuditLog).where(AuditLog.entity_type == "case", AuditLog.entity_id == str(case.id)).order_by(AuditLog.id))
    ]
    return CaseDetail(
        **base.model_dump(),
        decision_reason=case.decision_reason, decided_at=case.decided_at, decided_by_name=decided_by.name if decided_by else None,
        strategy_justification=case.strategy_justification, strategy_alternatives=case.strategy_alternatives, style_choice=case.style_choice,
        recommended_style=case.recommended_style, account_id=case.account_id, risk_breakdown=case.risk_breakdown, legal_note=case.legal_note,
        legal_at=case.legal_at, learning_context=case.learning_context, closed_reason=case.closed_reason, rating=case.rating, rating_note=case.rating_note,
        post=_post_out(ctx, post, PostDetail),
        classification=ClassificationOut.model_validate(cls) if cls else None,
        interpretation=InterpretationOut.model_validate(case.interpretation) if case.interpretation else None,
        facts=[fact_out(ctx.db, f) for f in case_svc.facts_for_case(ctx.db, case)],
        strategy_candidates=strategy_candidates(ctx.settings, case.stance, case.message_type) if case.flow else [],
        account_options=_account_options(ctx),
        timeline=timeline,
    )


@router.get("/cases", response_model=Page[CaseListItem])
def list_cases(
    ctx: Ctx = Depends(get_ctx),
    status: str | None = None,
    flow: str | None = None,
    alert_level: str | None = None,
    topic: str | None = None,
    stance: str | None = None,
    q: str | None = None,
    open_only: bool = False,
    order: str = Query("recent", pattern="^(recent|alert|risk)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
) -> Page[CaseListItem]:
    stmt = select(Case).where(Case.client_id == ctx.client_id)
    if status:
        stmt = stmt.where(Case.status.in_(status.split(",")))
    if flow:
        stmt = stmt.where(Case.flow == flow)
    if alert_level:
        stmt = stmt.where(Case.alert_level == alert_level)
    if topic:
        stmt = stmt.where(Case.topic_slug == topic)
    if stance:
        stmt = stmt.where(Case.stance == stance)
    if open_only:
        stmt = stmt.where(Case.status.not_in(case_svc.CLOSING | {"calificado"}))
    if q:
        stmt = stmt.join(Post, Post.id == Case.post_id).where(or_(Post.text.ilike(f"%{q}%"), Case.code.ilike(f"%{q}%")))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(ctx.db.scalars(stmt.order_by(Case.created_at.desc())))
    if order == "alert":
        rank = {"critico": 0, "alto": 1, "medio": 2, "sin_linea_base": 3, "bajo": 4}
        rows.sort(key=lambda c: (rank.get(c.alert_level or "bajo", 5), -(c.risk_score or 0)))
    elif order == "risk":
        rows.sort(key=lambda c: -(c.risk_score or 0))
    rows = rows[(page - 1) * page_size : page * page_size]
    return Page(items=[_list_item(ctx, c) for c in rows], total=total, page=page, page_size=page_size)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: int, ctx: Ctx = Depends(get_ctx)) -> CaseDetail:
    return _detail(ctx, owned(ctx.db, Case, case_id, ctx.client_id))


@router.patch("/cases/{case_id}/classification", response_model=CaseDetail)
def edit_classification(case_id: int, body: ClassificationPatch, ctx: Ctx = Depends(require("case.classify_edit"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    if case.status not in ("clasificado", "interpretado", "monitoreando", "ignorado"):
        raise AppError(409, "conflict", detail=case.status)
    cls = ctx.db.scalar(select(Classification).where(Classification.post_id == case.post_id))
    before = audit.snapshot(cls, ["stance", "topic_slug", "message_type", "recommendation", "canalizar_a_atencion"])
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(cls, k, v)
    if cls.message_type == "queja_ciudadana_legitima":
        cls.canalizar_a_atencion = True  # HR-05
    elif body.message_type is not None:
        cls.canalizar_a_atencion = False
    cls.edited_by_id, cls.edited_at = ctx.user.id, utcnow()
    case_svc.sync_case_from_classification(case, cls)
    if case.status in ("monitoreando", "ignorado"):
        case_svc.reopen(ctx.db, case, ctx.user, "clasificación editada")
    case_svc.reprocess(ctx.db, case, ctx.user)
    audit.record(ctx.db, action="classification.edit", entity_type="case", entity_id=case.id, client_id=ctx.client_id, user=ctx.user, before=before, after=audit.snapshot(cls, ["stance", "topic_slug", "message_type", "recommendation", "canalizar_a_atencion"]))
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/reinterpret", response_model=CaseDetail)
def reinterpret(case_id: int, ctx: Ctx = Depends(require("case.classify_edit"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    case_svc.reprocess(ctx.db, case, ctx.user)
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/decide", response_model=CaseDetail)
def decide(case_id: int, body: DecideIn, ctx: Ctx = Depends(require("case.decide"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    case_svc.decide(ctx.db, case, ctx.user, decision=body.decision, reason=body.reason, strategy=body.strategy, style_slug=body.style_slug, account_id=body.account_id)
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/legal", response_model=CaseDetail)
def legal(case_id: int, body: LegalIn, ctx: Ctx = Depends(require("legal.review"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    case_svc.legal_review(ctx.db, case, ctx.user, action=body.action, note=body.note)
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/close", response_model=CaseDetail)
def close(case_id: int, body: ReasonIn, ctx: Ctx = Depends(require("case.decide"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    case_svc.close_case(ctx.db, case, ctx.user, body.reason)
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/reopen", response_model=CaseDetail)
def reopen(case_id: int, body: ReasonIn, ctx: Ctx = Depends(require("case.decide"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    case_svc.reopen(ctx.db, case, ctx.user, body.reason)
    ctx.db.commit()
    return _detail(ctx, case)


@router.post("/cases/{case_id}/assign", response_model=CaseDetail)
def assign(case_id: int, body: AssignIn, ctx: Ctx = Depends(require("case.decide"))) -> CaseDetail:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    before = case.assigned_to_id
    case.assigned_to_id = body.user_id
    audit.record(ctx.db, action="case.assign", entity_type="case", entity_id=case.id, client_id=ctx.client_id, user=ctx.user, before={"assigned_to_id": before}, after={"assigned_to_id": body.user_id})
    ctx.db.commit()
    return _detail(ctx, case)


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(ctx: Ctx = Depends(get_ctx)) -> DashboardOut:
    cases = list(ctx.db.scalars(select(Case).where(Case.client_id == ctx.client_id)))
    open_cases = [c for c in cases if c.status not in case_svc.CLOSING | {"calificado"}]
    by_alert = Counter(c.alert_level or "bajo" for c in open_cases)
    by_status = Counter(c.status for c in cases)
    matrix = [{"alert": a, "status": s, "count": n} for (a, s), n in Counter((c.alert_level or "bajo", c.status) for c in cases).items()]
    since = utcnow() - timedelta(hours=48)
    posts = list(ctx.db.scalars(select(Post).where(Post.client_id == ctx.client_id, Post.is_history.is_(False), Post.published_at >= since, Post.alert_ratio.is_not(None)).order_by(Post.alert_ratio.desc()).limit(6)))
    case_by_post = {c.post_id: c for c in cases}
    accelerating = [
        {"post_id": p.id, "text": p.text[:160], "source": p.source.name if p.source else None, "alert_level": p.alert_level, "ratio": p.alert_ratio, "velocity": p.velocity,
         "case_id": case_by_post[p.id].id if p.id in case_by_post else None, "case_code": case_by_post[p.id].code if p.id in case_by_post else None}
        for p in posts
    ]
    repeated = []
    for c in open_cases:
        if c.interpretation and c.interpretation.repeated_in:
            repeated.append({"case_id": c.id, "code": c.code, "topic": c.topic_slug, "count": len(c.interpretation.repeated_in) + 1, "sources": [r["source"] for r in c.interpretation.repeated_in][:4]})
    repeated.sort(key=lambda r: r["count"], reverse=True)
    pending = {
        "decide": sum(1 for c in cases if c.status == "interpretado"),
        "legal": sum(1 for c in cases if c.status == "revision_legal"),
        "generate": sum(1 for c in cases if c.status == "listo_para_generar"),
        "review": sum(1 for c in cases if c.status in ("generado", "en_revision")),
    }
    recent = sorted(open_cases, key=lambda c: c.created_at, reverse=True)[:8]
    return DashboardOut(by_alert=dict(by_alert), by_status=dict(by_status), matrix=matrix, accelerating=accelerating, repeated=repeated[:6], pending=pending, recent_cases=[_list_item(ctx, c) for c in recent])
