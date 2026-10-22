"""Response risk score (0–100), explainable and rule-based with configurable weights. Never computed by the LLM."""

from typing import Any

from app.i18n import t
from app.services.client_settings import ClientSettings

ALERT_FACTOR = {"bajo": 0.1, "sin_linea_base": 0.35, "medio": 0.4, "alto": 0.7, "critico": 1.0}
TYPE_FACTOR = {"opinion": 0.2, "queja_ciudadana_legitima": 0.3, "dato_sacado_de_contexto": 0.5, "dato_falso": 0.6, "acusacion_o_difamacion": 1.0}
STYLE_FACTOR = {"bajo": 0.1, "medio": 0.5, "alto": 1.0}


def compute_risk(
    settings: ClientSettings,
    *,
    alert_level: str | None,
    message_type: str | None,
    stance: str | None,
    style_risk: str | None,
    unverified_figures: int,
    actors_named: list[str],
    veda_active: bool,
    red_team: dict[str, int] | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    w = settings.risk_weights
    red_team = red_team or {}
    type_value = 0.1 if stance == "a_favor" and message_type == "opinion" else TYPE_FACTOR.get(message_type or "opinion", 0.2)
    rt_value = min(1.0, red_team.get("alta", 0) * 0.34 + red_team.get("media", 0) * 0.15 + red_team.get("baja", 0) * 0.05)
    factors = [
        ("alert_level", w.alert_level, ALERT_FACTOR.get(alert_level or "bajo", 0.1), alert_level or "—"),
        ("message_type", w.message_type, type_value, message_type or "—"),
        ("style_risk", w.style_risk, STYLE_FACTOR.get(style_risk or "bajo", 0.1), style_risk or "—"),
        ("unverified_figures", w.unverified_figures, min(1.0, unverified_figures / 4), str(unverified_figures)),
        ("names_actors", w.names_actors, 1.0 if actors_named else 0.0, ", ".join(actors_named) or "—"),
        ("veda_active", w.veda_active, 1.0 if veda_active else 0.0, t("common.yes") if veda_active else t("common.no")),
        ("red_team", w.red_team, rt_value, f"{red_team.get('alta', 0)}/{red_team.get('media', 0)}/{red_team.get('baja', 0)}"),
    ]
    breakdown = []
    total = 0.0
    for key, weight, value, raw in factors:
        points = round(weight * value, 1)
        total += points
        breakdown.append({"factor": key, "label": t(f"risk.{key}.label"), "raw": raw, "value": round(value, 2), "weight": weight, "points": points, "explanation": t(f"risk.{key}.explanation", raw=raw)})
    max_total = sum(f[1] for f in factors) or 100
    return int(round(100 * total / max_total)), breakdown
