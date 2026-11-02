from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORM

StyleStatus = Literal["borrador", "revision", "activo", "archivado"]
DirectiveType = Literal["narrativa", "estilo", "linea_roja", "leyenda", "vocabulario", "prioridad_tematica"]
DirectiveStatus = Literal["borrador", "en_revision", "activa", "archivada", "rechazada"]
Risk = Literal["bajo", "medio", "alto"]


class TagOut(ORM):
    id: int
    slug: str
    name: str
    ord: int


class TagDimensionOut(ORM):
    id: int
    slug: str
    name: str
    kind: str
    min_value: int | None
    max_value: int | None
    tags: list[TagOut]


class TagIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str


class TagDimensionIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    kind: Literal["categorical", "numeric"] = "categorical"


class StyleFields(BaseModel):
    name: str
    description: str = ""
    tags: dict[str, list[str]] = {}
    free_tags: list[str] = []
    intensity_min: int = Field(1, ge=1, le=5)
    intensity_max: int = Field(2, ge=1, le=5)
    voice: dict[str, Any] = {"persona": "nosotros_institucional", "trato": "usted", "idioma": "es-MX"}
    guidelines: dict[str, list[str]] = {"haz": [], "evita": []}
    preferred_vocab: list[str] = []
    prohibited_vocab: list[str] = []
    length: dict[str, Any] = {"copy_principal": {"min": 120, "max": 280, "unidad": "caracteres"}}
    emoji_usage: Literal["ninguno", "moderado"] = "ninguno"
    caps_usage: Literal["normal", "solo_rotulos"] = "normal"
    good_examples: list[str] = []
    bad_examples: list[str] = []
    visual_guide: str = ""
    palette: list[str] = []
    allowed_formats: list[str] = []
    risk: Risk = "bajo"
    requires_legal: bool = False


class StyleIn(StyleFields):
    slug: str = Field(pattern=r"^[a-z0-9_]+$")


class StylePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: dict[str, list[str]] | None = None
    free_tags: list[str] | None = None
    intensity_min: int | None = Field(None, ge=1, le=5)
    intensity_max: int | None = Field(None, ge=1, le=5)
    voice: dict[str, Any] | None = None
    guidelines: dict[str, list[str]] | None = None
    preferred_vocab: list[str] | None = None
    prohibited_vocab: list[str] | None = None
    length: dict[str, Any] | None = None
    emoji_usage: Literal["ninguno", "moderado"] | None = None
    caps_usage: Literal["normal", "solo_rotulos"] | None = None
    good_examples: list[str] | None = None
    bad_examples: list[str] | None = None
    visual_guide: str | None = None
    palette: list[str] | None = None
    allowed_formats: list[str] | None = None
    risk: Risk | None = None
    requires_legal: bool | None = None
    change_note: str | None = None


class StyleOut(StyleFields, ORM):
    id: int
    client_id: int | None
    slug: str
    version: int
    status: StyleStatus
    parent_id: int | None
    change_note: str
    legal_approved_at: datetime | None
    legal_approved_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    is_base: bool = False
    versions: list[dict[str, Any]] = []


class StyleTransitionIn(BaseModel):
    status: StyleStatus
    note: str = ""


class StyleTestIn(BaseModel):
    text: str | None = None
    flow: Literal["A", "B"] | None = None


class StyleTestOut(BaseModel):
    sample: str
    topic: str | None
    strategy: str
    flow: str
    segments: list[dict[str, Any]]
    text: str
    why: str
    missing_data: list[str]
    lint_status: str
    findings: list[dict[str, Any]]
    resolved: dict[str, Any]
    style_block: str
    ai_run_id: int


class ResolvePreviewIn(BaseModel):
    style_slug: str
    topic: str | None = None
    format_slug: str | None = None
    account_id: int | None = None
    flow: Literal["A", "B"] | None = None
    intensity: int | None = None


class DirectiveFields(BaseModel):
    dtype: DirectiveType
    title: str = Field(min_length=3)
    text: str = ""
    structured: dict[str, Any] = {}
    scope: dict[str, list[Any]] = {}
    mandatory: Literal["obligatoria", "sugerida"] = "sugerida"
    priority: int = Field(50, ge=1, le=100)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class DirectivePatch(BaseModel):
    dtype: DirectiveType | None = None
    title: str | None = None
    text: str | None = None
    structured: dict[str, Any] | None = None
    scope: dict[str, list[Any]] | None = None
    mandatory: Literal["obligatoria", "sugerida"] | None = None
    priority: int | None = Field(None, ge=1, le=100)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class DirectiveOut(DirectiveFields, ORM):
    id: int
    code: str
    version: int
    status: DirectiveStatus
    conflict_status: str
    conflict_report: dict[str, Any]
    rejection_reason: str
    created_by_name: str | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    in_force: bool = False


class DirectiveTransitionIn(BaseModel):
    status: DirectiveStatus
    note: str = ""


class FindingDecisionIn(BaseModel):
    finding_id: str
    confirmed: bool


class FormatOut(ORM):
    id: int
    slug: str
    code: str
    name: str
    description: str
    default_style_slug: str
    allowed_style_slugs: list[str]
    template: str
    options: dict[str, Any]
    active: bool


class FormatPatch(BaseModel):
    name: str | None = None
    template: str | None = None
    description: str | None = None
    default_style_slug: str | None = None
    allowed_style_slugs: list[str] | None = None
    options: dict[str, Any] | None = None
    active: bool | None = None


class CreativeTypeOut(ORM):
    id: int
    slug: str
    code: str
    flow: str
    name: str
    description: str
    required_slots: list[str]
    template: str
    requires_fact: bool
    requires_consent: bool
    requires_real_photo: bool
    text_only: bool
    is_comparison: bool
    active: bool


class FormatIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=80)
    name: str = Field(min_length=2)
    description: str = ""
    template: str = "clasico"  # one of the render frames: clasico, contexto, historieta, titeres, comparativa, voz_pueblo
    default_style_slug: str = "cercano"
    allowed_style_slugs: list[str] = []
    options: dict[str, Any] = {}


class CreativeTypeIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=80)
    name: str = Field(min_length=2)
    description: str = ""
    flow: Literal["A", "B"] = "A"
    template: str = "dato_duro"
    required_slots: list[str] = ["titulo", "texto"]
    requires_fact: bool = False
    requires_consent: bool = False
    requires_real_photo: bool = False
    text_only: bool = False


class CreativeTypePatch(BaseModel):
    name: str | None = None
    flow: Literal["A", "B"] | None = None
    template: str | None = None
    text_only: bool | None = None
    description: str | None = None
    required_slots: list[str] | None = None
    requires_fact: bool | None = None
    requires_consent: bool | None = None
    requires_real_photo: bool | None = None
    active: bool | None = None


class MatrixCell(BaseModel):
    creative_slug: str
    format_slug: str
    level: Literal["full", "partial", "none"]
    note: str = ""


class MatrixOut(BaseModel):
    creatives: list[CreativeTypeOut]
    formats: list[FormatOut]
    cells: list[MatrixCell]


class RestrictionOut(ORM):
    id: int
    name: str
    active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    blocked_formats: list[str]
    blocked_creatives: list[str]
    mandatory_legends: list[str]
    reason: str
    in_effect: bool = False


class RestrictionIn(BaseModel):
    name: str
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    blocked_formats: list[str] = []
    blocked_creatives: list[str] = []
    mandatory_legends: list[str] = []
    reason: str = ""


class AiRunOut(ORM):
    id: int
    step: str
    prompt_version: str
    provider: str
    model: str
    status: str
    error: str
    attempts: int
    latency_ms: int
    style_slug: str | None
    style_version: int | None
    applied_directives: list[dict[str, Any]]
    case_id: int | None
    piece_id: int | None
    created_at: datetime


class AiRunDetail(AiRunOut):
    input: dict[str, Any]
    output: dict[str, Any] | None
