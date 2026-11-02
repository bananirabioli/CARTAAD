from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM
from app.schemas.kb import FactOut


class FigureOut(ORM):
    id: int
    piece_version: int
    raw: str
    kind: str
    value: float | None
    unit: str | None
    location: str
    fact_id: int | None
    matched: bool
    status: str
    verified_by_id: int | None
    verified_at: datetime | None


class RedTeamNoteOut(ORM):
    id: int
    piece_version: int
    kind: str
    severity: str
    text: str
    target: str


class VersionOut(ORM):
    id: int
    version: int
    style_slug: str
    style_version: int
    strategy: str
    intensity: int
    author_type: str
    author_id: int | None
    author_name: str | None = None
    action: str
    instruction: str
    note: str
    diff: list[dict[str, Any]]
    created_at: datetime


class VersionDetail(VersionOut):
    content: dict[str, Any]


class PieceOut(ORM):
    id: int
    proposal_id: int
    case_id: int
    kind: str
    creative_slug: str | None
    format_slug: str
    account_id: int | None
    flow: str
    style_slug: str
    style_version: int
    strategy: str
    intensity: int
    effective_tags: list[str]
    applied_directives: list[dict[str, Any]]
    adaptation: str | None
    why: str
    content: dict[str, Any]
    missing_inputs: list[str]
    renders: list[str]
    render_status: str
    render_error: str = ""
    status: str
    validation: list[dict[str, Any]]
    validation_status: str
    compliance: dict[str, Any]
    risk_score: int | None
    risk_breakdown: list[dict[str, Any]]
    red_team_summary: dict[str, int]
    legal_required: bool
    legal_status: str
    legal_reason: str
    legal_note: str
    current_version: int
    approved_version: int | None
    approved_at: datetime | None
    discard_reason: str
    created_at: datetime
    updated_at: datetime
    figures_total: int = 0
    figures_verified: int = 0
    case_code: str | None = None
    account_handle: str | None = None
    approvable: bool = False
    approval_blockers: list[str] = []


class PieceDetail(PieceOut):
    figures: list[FigureOut] = []
    red_team_notes: list[RedTeamNoteOut] = []
    versions: list[VersionOut] = []
    facts: list[FactOut] = []
    consent: dict[str, Any] | None = None
    reviews: list[dict[str, Any]] = []
    style_intensity: list[int] = []
    allowed_styles: list[str] = []


class ProposalOut(ORM):
    id: int
    case_id: int
    account_id: int | None
    format_slug: str
    flow: str
    strategy: str
    variant_styles: list[str]
    status: str
    error: str
    excluded_creatives: list[dict[str, Any]]
    learning_context: dict[str, Any]
    options: dict[str, Any] = {}
    created_at: datetime
    finished_at: datetime | None
    pieces: list[PieceOut] = []
    facts: list[FactOut] = []


class GenerateIn(BaseModel):
    variant_styles: list[str] | None = None


class GenerateContentIn(BaseModel):
    """MVP: decide + generate in one step (copies, image prompts and images, optional video)."""

    strategy: Literal["desmentir", "contextualizar", "reencuadrar", "contrastar", "amplificar", "agradecer"] | None = None
    style_slug: str | None = None
    variant_styles: list[str] | None = None
    network: Literal["facebook", "x", "instagram", "tiktok", "youtube", "whatsapp"] = "facebook"
    image_count: int = Field(default=1, ge=0, le=2)
    video: bool = False
    instructions: str = Field(default="", max_length=1000)


class CopilotIn(BaseModel):
    action: Literal["mas_corto", "mas_firme", "mas_formal", "menos_formal", "mas_empatico", "otro_angulo", "agregar_dato", "cambiar_estilo", "libre"]
    instruction: str = ""
    style_slug: str | None = None


class CopilotOut(BaseModel):
    applied: bool
    message: str
    version: int | None = None
    suggested_style: str | None = None
    rule_id: str | None = None
    piece: PieceDetail


class ContentIn(BaseModel):
    segments: list[dict[str, Any]] | None = None
    slots: dict[str, dict[str, Any]] | None = None
    slides: list[dict[str, Any]] | None = None
    images: list[dict[str, Any]] | None = None
    note: str = ""


class RevertIn(BaseModel):
    version: int = Field(ge=1)


class VerifyFigureIn(BaseModel):
    status: Literal["verificada", "rechazada"] = "verificada"
    note: str = ""


class PieceLegalIn(BaseModel):
    action: Literal["liberar", "bloquear"]
    note: str
