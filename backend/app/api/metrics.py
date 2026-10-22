"""Medición (6.8): métricas por variante (A/B), calificación y rankings por tema."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import Ctx, get_ctx, owned, require
from app.models.cases import Case
from app.services import metrics as svc
from app.services.learning import learning_context

router = APIRouter(tags=["metrics"])


class MetricsIn(BaseModel):
    piece_id: int
    reach: int = Field(ge=0)
    impressions: int = Field(0, ge=0)
    likes: int = Field(0, ge=0)
    comments: int = Field(0, ge=0)
    shares: int = Field(0, ge=0)
    sentiment_pos: float = Field(0, ge=0, le=1)
    sentiment_neg: float = Field(0, ge=0, le=1)
    sentiment_neu: float = Field(0, ge=0, le=1)
    original_reach: int | None = Field(None, ge=0)
    note: str = ""


class RateIn(BaseModel):
    outcome: str = Field(pattern="^(funciono|no_funciono)$")
    note: str = ""


class CaseMetricsOut(BaseModel):
    case_id: int
    status: str
    rating: str | None
    original_reach: int
    original_sentiment_neg: float
    variants: list[dict]


def _out(ctx: Ctx, case: Case) -> CaseMetricsOut:
    reach, neg = svc.original_baseline(ctx.db, case)
    return CaseMetricsOut(case_id=case.id, status=case.status, rating=case.rating, original_reach=reach, original_sentiment_neg=neg, variants=svc.variant_summary(ctx.db, case))


@router.get("/cases/{case_id}/metrics", response_model=CaseMetricsOut)
def case_metrics(case_id: int, ctx: Ctx = Depends(get_ctx)) -> CaseMetricsOut:
    return _out(ctx, owned(ctx.db, Case, case_id, ctx.client_id))


@router.post("/cases/{case_id}/metrics", response_model=CaseMetricsOut)
def add_metrics(case_id: int, body: MetricsIn, ctx: Ctx = Depends(require("metrics.record"))) -> CaseMetricsOut:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    svc.record_metrics(ctx.db, case, ctx.user, body.model_dump())
    ctx.db.commit()
    return _out(ctx, case)


@router.post("/cases/{case_id}/metrics/simulate", response_model=CaseMetricsOut)
def simulate(case_id: int, ctx: Ctx = Depends(require("metrics.record"))) -> CaseMetricsOut:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    svc.simulate_metrics(ctx.db, case, ctx.user)
    ctx.db.commit()
    return _out(ctx, case)


@router.post("/cases/{case_id}/rate", response_model=CaseMetricsOut)
def rate(case_id: int, body: RateIn, ctx: Ctx = Depends(require("case.rate"))) -> CaseMetricsOut:
    case = owned(ctx.db, Case, case_id, ctx.client_id)
    svc.rate_case(ctx.db, case, ctx.user, body.outcome, body.note)
    ctx.db.commit()
    return _out(ctx, case)


@router.get("/metrics/rankings", response_model=dict)
def rankings(ctx: Ctx = Depends(get_ctx), topic: str | None = None) -> dict:
    return svc.rankings(ctx.db, ctx.client_id, topic, ctx.settings.learning_min_sample)


@router.get("/metrics/learning", response_model=dict)
def learning(ctx: Ctx = Depends(get_ctx), topic: str | None = None) -> dict:
    """The learning context fed to the strategy recommender and the generator."""
    return learning_context(ctx.db, ctx.client_id, topic, ctx.settings.learning_min_sample)


@router.get("/metrics/experiments", response_model=list[dict])
def experiments(ctx: Ctx = Depends(get_ctx)) -> list[dict]:
    """A/B: cases with more than one measured variant."""
    from sqlalchemy import func, select

    from app.models.metrics import PostMetrics

    case_ids = [cid for cid, n in ctx.db.execute(
        select(PostMetrics.case_id, func.count(func.distinct(PostMetrics.piece_id))).where(PostMetrics.client_id == ctx.client_id).group_by(PostMetrics.case_id)
    ) if n >= 1]
    out = []
    for cid in case_ids:
        case = ctx.db.get(Case, cid)
        out.append({"case_id": cid, "code": case.code, "topic": case.topic_slug, "status": case.status, "rating": case.rating, "variants": svc.variant_summary(ctx.db, case)})
    return out
