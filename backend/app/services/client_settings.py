"""Per-client configurable settings (thresholds, weights, mappings). Stored as JSON overrides on Client.settings."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.core import Client

ValidatorMode = Literal["block", "warn"]


class AlertThresholds(BaseModel):
    medio: float = 1.5
    alto: float = 3.0
    critico: float = 6.0


class RiskWeights(BaseModel):
    alert_level: float = 20
    message_type: float = 20
    style_risk: float = 15
    unverified_figures: float = 15
    names_actors: float = 10
    veda_active: float = 10
    red_team: float = 10


class ValidatorModes(BaseModel):
    fact_without_document: ValidatorMode = "block"
    fact_expired: ValidatorMode = "block"
    unbacked_actor_mention: ValidatorMode = "block"


AiLayer = Literal["analysis", "text", "image", "video"]  # text = copies
AI_LAYERS: tuple[str, ...] = ("analysis", "text", "image", "video")


class AiModels(BaseModel):
    """OpenRouter model id per layer; None means the .env default."""

    analysis: str | None = None
    text: str | None = None  # copies
    image: str | None = None
    video: str | None = None


class AiGuides(BaseModel):
    """Free-text creative guide per layer, injected into the prompts (Laboratorio → Guías)."""

    analysis: str = ""
    text: str = ""  # copies
    image: str = ""
    video: str = ""


class RuleConfig(BaseModel):
    enabled: bool = True
    text: str | None = None


class ClientSettings(BaseModel):
    context: str = ""  # region / who the client is; goes into the analyze and generate prompts
    ai_models: AiModels = Field(default_factory=AiModels)
    ai_guides: AiGuides = Field(default_factory=AiGuides)
    rules: dict[str, RuleConfig] = Field(default_factory=dict)
    facts_top_k: int = Field(default=8, ge=1, le=25)
    alert_thresholds: AlertThresholds = Field(default_factory=AlertThresholds)
    alert_window_hours: float = 6
    baseline_min_days: int = 14
    learning_min_sample: int = 5
    risk_weights: RiskWeights = Field(default_factory=RiskWeights)
    validator_modes: ValidatorModes = Field(default_factory=ValidatorModes)
    strategy_mapping: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "dato_falso": ["desmentir"],
            "dato_sacado_de_contexto": ["contextualizar"],
            "acusacion_o_difamacion": ["reencuadrar", "contrastar"],
            "opinion": ["contextualizar", "reencuadrar"],
            "queja_ciudadana_legitima": ["contextualizar"],
            "a_favor": ["amplificar", "agradecer"],
        }
    )
    default_variant_styles: list[str] = Field(default_factory=lambda: ["institucional", "cercano", "directo"])
    complaint_style: str = "empatico"
    creatives_min: int = 5
    creatives_max: int = 10
    source_review_interval_days: int = 30
    sources_last_reviewed_at: str | None = None
    coordinated_window_hours: int = 72
    coordinated_similarity: float = 0.75
    repeated_similarity: float = 0.5
    neutral_label_flow_b: str = "DATO"
    alert_label_flow_a: str = "ALERTA · CONTEXTO"
    comparativa_closing: str = "Mismo periodo, misma base: compare usted."
    attribution_verbs: list[str] = Field(
        default_factory=lambda: [
            "hizo",
            "hicieron",
            "nunca ha",
            "nunca han",
            "oculto",
            "ocultaron",
            "robo",
            "robaron",
            "desvio",
            "desviaron",
            "mintio",
            "mintieron",
            "prometio",
            "abandono",
            "abandonaron",
            "no ha hecho",
            "no hizo",
            "no han hecho",
            "dejo",
            "dejaron",
            "gasto",
            "gastaron",
            "recorto",
            "recortaron",
            "es responsable",
            "son responsables",
            "tiene la culpa",
            "tienen la culpa",
        ]
    )


def get_client_settings(client: Client) -> ClientSettings:
    return ClientSettings.model_validate(client.settings or {})


def rules_dict(settings: ClientSettings) -> dict[str, dict[str, Any]]:
    return {k: v.model_dump() for k, v in settings.rules.items()}


def rules_for(obj: Any) -> dict[str, dict[str, Any]]:
    """Client rules for any ORM object with client_id (case, piece…), through its session."""
    from sqlalchemy.orm import object_session

    db = object_session(obj)
    client = db.get(Client, obj.client_id) if db is not None and getattr(obj, "client_id", None) else None
    return rules_dict(get_client_settings(client)) if client else {}


def update_client_settings(client: Client, patch: dict[str, Any]) -> ClientSettings:
    from app.errors import AppError
    from app.guardrails.hard_rules import HardRuleViolation, validate_rules_patch

    merged = get_client_settings(client).model_dump()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    settings = ClientSettings.model_validate(merged)
    try:
        validate_rules_patch(rules_dict(settings))
    except HardRuleViolation as exc:
        raise AppError(422, "hard_rule", exc.message, details={"rule_id": exc.rule_id}) from exc
    client.settings = settings.model_dump()
    return settings
