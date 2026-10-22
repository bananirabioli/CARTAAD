from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.schemas.common import ORM
from app.schemas.kb import FactOut
from app.schemas.monitoring import PostDetail

Decision = Literal["responder", "monitorear", "ignorar", "canalizar"]


class ClassificationOut(ORM):
    stance: str
    topic_slug: str
    message_type: str
    alert_level: str | None
    alert_ratio: float | None
    velocity: float | None
    recommendation: str
    confidence: float
    explanation: str
    canalizar_a_atencion: bool
    edited_at: datetime | None
    ai_run_id: int | None


class ClassificationPatch(BaseModel):
    stance: Literal["a_favor", "en_contra", "neutral"] | None = None
    topic_slug: str | None = None
    message_type: Literal["opinion", "dato_falso", "dato_sacado_de_contexto", "acusacion_o_difamacion", "queja_ciudadana_legitima"] | None = None
    recommendation: Literal["responder", "monitorear", "ignorar"] | None = None


class ClaimOut(ORM):
    id: int
    text: str
    verdict: str
    fact_ids: list[int]
    explanation: str
    missing_data: str | None


class InterpretationOut(ORM):
    summary: str
    narrative: str
    missing_context: list[dict[str, Any]]
    comments_summary: list[dict[str, Any]]
    repeated_in: list[dict[str, Any]]
    claims: list[ClaimOut]
    ai_run_id: int | None


class CaseListItem(ORM):
    id: int
    code: str
    status: str
    flow: str | None
    topic_slug: str | None
    message_type: str | None
    stance: str | None
    alert_level: str | None
    decision: str | None
    strategy: str | None
    strategy_suggested: str | None
    style_slug: str | None
    risk_score: int | None
    legal_required: bool
    legal_status: str
    canalizar_a_atencion: bool
    created_at: datetime
    updated_at: datetime
    post_id: int
    post_text: str = ""
    source_name: str | None = None
    network: str | None = None
    alert_ratio: float | None = None
    recommendation: str | None = None
    assigned_to_name: str | None = None
    pieces_count: int = 0


class AccountOption(BaseModel):
    id: int
    handle: str
    display_name: str
    account_type: str
    network: str
    format_slug: str
    format_name: str
    allowed_styles: list[str]
    default_style: str | None
    default_source: str


class CaseDetail(CaseListItem):
    decision_reason: str
    decided_at: datetime | None
    decided_by_name: str | None = None
    strategy_justification: str
    strategy_alternatives: list[dict[str, Any]]
    style_choice: dict[str, Any]
    recommended_style: dict[str, Any]
    account_id: int | None
    risk_breakdown: list[dict[str, Any]]
    legal_note: str
    legal_at: datetime | None
    learning_context: dict[str, Any]
    closed_reason: str
    rating: str | None
    rating_note: str
    post: PostDetail
    classification: ClassificationOut | None
    interpretation: InterpretationOut | None
    facts: list[FactOut] = []
    strategy_candidates: list[str] = []
    account_options: list[AccountOption] = []
    timeline: list[dict[str, Any]] = []


class DecideIn(BaseModel):
    decision: Decision
    reason: str = ""
    strategy: Literal["desmentir", "contextualizar", "reencuadrar", "contrastar", "amplificar", "agradecer"] | None = None
    style_slug: str | None = None
    account_id: int | None = None


class LegalIn(BaseModel):
    action: Literal["liberar", "bloquear"]
    note: str


class ReasonIn(BaseModel):
    reason: str


class AssignIn(BaseModel):
    user_id: int | None


class DashboardOut(BaseModel):
    by_alert: dict[str, int]
    by_status: dict[str, int]
    matrix: list[dict[str, Any]]
    accelerating: list[dict[str, Any]]
    repeated: list[dict[str, Any]]
    pending: dict[str, int]
    recent_cases: list[CaseListItem]
