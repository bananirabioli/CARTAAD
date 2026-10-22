"""Structured outputs per AI step. These Pydantic models are the source of /schemas/*.json."""

from typing import Literal

from pydantic import BaseModel, Field

Stance = Literal["a_favor", "en_contra", "neutral"]
MessageType = Literal["opinion", "dato_falso", "dato_sacado_de_contexto", "acusacion_o_difamacion", "queja_ciudadana_legitima"]
Recommendation = Literal["responder", "monitorear", "ignorar"]
Verdict = Literal["cierta", "falsa", "incompleta", "no_verificable"]
Strategy = Literal["desmentir", "contextualizar", "reencuadrar", "contrastar", "amplificar", "agradecer"]
SegmentType = Literal["asercion_factual", "opinion_marcada", "pregunta", "llamado", "saludo"]


class Segment(BaseModel):
    text: str
    type: SegmentType
    fact_ids: list[int] = Field(default_factory=list, description="Obligatorio (≥1) si type = asercion_factual.")


class OcrVisionOut(BaseModel):
    extracted_text: str = Field(description="Texto legible en la captura, tal cual.")
    visual_context: str = Field(description="Descripción breve del contexto visual (sin identificar personas).")
    detected_names: list[str] = Field(default_factory=list, description="Nombres o handles visibles (para difuminar), no se almacenan.")


class ClassifyOut(BaseModel):
    stance: Stance
    topic: str = Field(description="slug de uno de los temas del cliente, o 'otro'")
    message_type: MessageType
    recommendation: Recommendation
    confidence: float = Field(ge=0, le=1)
    explanation: str = Field(description="Por qué esta clasificación y recomendación; si responder amplificaría el ataque, decirlo.")
    canalizar_a_atencion: bool = False


class ClaimOut(BaseModel):
    text: str
    verdict: Verdict
    fact_ids: list[int] = Field(default_factory=list)
    explanation: str
    missing_data: str | None = Field(default=None, description="Qué dato falta en la base para verificarla.")


class MissingContextOut(BaseModel):
    description: str
    needs_kb_owner: bool = True


class CommentThemeOut(BaseModel):
    theme: str
    share: float = Field(ge=0, le=1)
    summary: str


class InterpretOut(BaseModel):
    summary: str
    narrative: str
    claims: list[ClaimOut]
    missing_context: list[MissingContextOut] = Field(default_factory=list)
    comments_summary: list[CommentThemeOut] = Field(default_factory=list)


class StrategyAlternative(BaseModel):
    strategy: Strategy
    why: str


class RecommendStrategyOut(BaseModel):
    strategy: Strategy
    justification: str
    alternatives: list[StrategyAlternative] = Field(default_factory=list)


class GenerateCopyOut(BaseModel):
    segments: list[Segment]
    why: str
    adaptation: str | None = None
    missing_data: list[str] = Field(default_factory=list)


class SlotValue(BaseModel):
    name: str
    text: str = ""
    fact_ids: list[int] = Field(default_factory=list)


class SlideValue(BaseModel):
    title: str
    text: str
    fact_ids: list[int] = Field(default_factory=list)


class Comparison(BaseModel):
    left: list[int]
    right: list[int]
    mode: Literal["comparativa", "antes_despues"] = "comparativa"


class CreativeDraft(BaseModel):
    creative_slug: str
    why: str
    adaptation: str | None = None
    slots: list[SlotValue] = Field(default_factory=list)
    slides: list[SlideValue] = Field(default_factory=list)
    image_ids: list[int] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    comparison: Comparison | None = Field(default=None, description="Para comparaciones: fact_ids de cada lado (mismo periodo y misma base).")


class GenerateCreativesOut(BaseModel):
    creatives: list[CreativeDraft]


class RefinePieceOut(BaseModel):
    refused: bool = False
    refusal_reason: str | None = None
    suggested_style: str | None = None
    note: str = ""
    segments: list[Segment] = Field(default_factory=list)
    slots: list[SlotValue] = Field(default_factory=list)
    slides: list[SlideValue] = Field(default_factory=list)


class RedTeamNoteOut(BaseModel):
    kind: Literal["replica", "punto_debil"]
    severity: Literal["baja", "media", "alta"]
    text: str
    target: str = ""


class RedTeamOut(BaseModel):
    notes: list[RedTeamNoteOut]


class DirectiveConflictOut(BaseModel):
    directive_code: str
    explanation: str
    severity: Literal["advertencia", "bloqueante"] = "advertencia"


class CheckDirectiveOut(BaseModel):
    conflicts: list[DirectiveConflictOut] = Field(default_factory=list)


STEP_MODELS: dict[str, type[BaseModel]] = {
    "ocr_vision": OcrVisionOut,
    "classify": ClassifyOut,
    "interpret": InterpretOut,
    "recommend_strategy": RecommendStrategyOut,
    "generate_copy": GenerateCopyOut,
    "generate_creatives": GenerateCreativesOut,
    "refine_piece": RefinePieceOut,
    "red_team": RedTeamOut,
    "check_directive": CheckDirectiveOut,
}
