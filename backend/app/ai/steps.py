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


# ------------------------------------------------------------------ MVP: one call to analyze, one call to generate


class AnalyzeCaptureOut(BaseModel):
    extracted_text: str = Field(description="Texto visible de la publicación, tal cual (sin los comentarios).")
    network_guess: Literal["facebook", "x", "instagram", "tiktok", "youtube", "whatsapp", "otra"] = "otra"
    visual_context: str = Field(description="Qué se ve: imagen, video, memes, tono visual. Sin identificar personas por su rostro.")
    author_type: Literal["medio", "pagina_ciudadana", "actor_politico", "influencer", "cuenta_personal", "desconocido"] = "desconocido"
    stance: Stance = Field(description="Postura de la publicación respecto al cliente.")
    stance_confidence: float = Field(ge=0, le=1)
    topic: str = Field(description="slug de uno de los temas del cliente, u 'otro'")
    message_type: MessageType
    tone: list[str] = Field(default_factory=list, description="Rasgos de tono: ironía, enojo, burla, preocupación, entusiasmo…")
    summary: str = Field(description="Qué dice la publicación y qué busca, en 2–3 frases.")
    narrative: str = Field(description="La narrativa de fondo que empuja (el marco), en una frase.")
    claims: list[ClaimOut] = Field(default_factory=list)
    audience_reaction: list[CommentThemeOut] = Field(default_factory=list, description="Temas de los comentarios visibles, sin identificar a nadie.")
    risk_notes: str = Field(default="", description="Riesgos de responder o de no responder.")
    recommendation: Recommendation
    explanation: str = Field(description="Por qué esta recomendación; si responder amplificaría el ataque, dilo.")
    strategy: Strategy
    strategy_justification: str
    alternatives: list[StrategyAlternative] = Field(default_factory=list)
    canalizar_a_atencion: bool = False
    detected_names: list[str] = Field(default_factory=list, description="Nombres o handles visibles de particulares, solo para difuminarlos.")


class CopyVariantOut(BaseModel):
    style: str = Field(description="slug del estilo de esta variante (uno de los entregados).")
    segments: list[Segment]
    hashtags: list[str] = Field(default_factory=list)
    cta: str = ""
    why: str


class ImagePromptOut(BaseModel):
    concept: str = Field(description="Idea de la imagen en español, para la persona que revisa.")
    prompt: str = Field(description="Prompt en inglés para el modelo de imagen: escena, encuadre, luz, paleta, estilo.")
    negative_prompt: str = ""
    aspect_ratio: Literal["1:1", "4:5", "9:16", "16:9"] = "4:5"
    headline: str = Field(default="", description="Titular corto en español que el sistema superpone sobre la imagen.")


class VideoScene(BaseModel):
    seconds: int = Field(ge=1, le=30)
    visual: str
    voiceover: str = ""


class VideoPlanOut(BaseModel):
    concept: str
    scenes: list[VideoScene] = Field(default_factory=list)
    prompt: str = Field(description="Prompt en inglés para el modelo de video: acción, cámara, luz, ritmo.")
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = "9:16"
    voiceover_full: str = Field(default="", description="Guion completo de voz en off en español.")
    on_screen_text: list[str] = Field(default_factory=list, description="Textos a sobreponer en edición; el modelo de video no los dibuja.")


class GenerateContentOut(BaseModel):
    copies: list[CopyVariantOut]
    image_prompts: list[ImagePromptOut] = Field(default_factory=list)
    video: VideoPlanOut | None = None
    missing_data: list[str] = Field(default_factory=list)


STEP_MODELS: dict[str, type[BaseModel]] = {
    "analyze_capture": AnalyzeCaptureOut,
    "generate_content": GenerateContentOut,
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
