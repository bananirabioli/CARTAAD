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


class ClientSettings(BaseModel):
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


def update_client_settings(client: Client, patch: dict[str, Any]) -> ClientSettings:
    merged = get_client_settings(client).model_dump()
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    settings = ClientSettings.model_validate(merged)
    client.settings = settings.model_dump()
    return settings
