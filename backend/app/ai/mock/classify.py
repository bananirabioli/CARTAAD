"""classify (mock): keyword rules from fixtures/mock/classify_rules.json. The alert level comes from code."""

import re
from typing import Any

from app.ai.mock.fixtures import mock_json
from app.textnorm import normalize

_NUMBER = re.compile(r"\d")
ALERT_RANK = {"bajo": 0, "sin_linea_base": 1, "medio": 1, "alto": 2, "critico": 3}


def _hits(text: str, words: list[str]) -> list[str]:
    return [w for w in words if normalize(w) in text]


def detect_topic(text: str, topics: list[dict[str, Any]]) -> str:
    padded = f" {text} "
    best, best_score = "otro", 0
    for topic in topics:
        score = sum(1 for kw in topic.get("keywords", []) if f" {normalize(kw)}" in padded)
        if score > best_score:
            best, best_score = topic["slug"], score
    return best


def classify(ctx: dict[str, Any]) -> dict[str, Any]:
    rules = mock_json("classify_rules")
    post = ctx.get("post") or {}
    text = normalize(f"{post.get('text', '')} {post.get('image_text', '')}")
    mtype, type_hits = "opinion", []
    for rule in rules["message_type"]:
        hits = _hits(text, rule["any"])
        if hits and (not rule.get("requires_number") or _NUMBER.search(text)):
            mtype, type_hits = rule["type"], hits
            break
    stance_hits = {k: _hits(text, v) for k, v in rules["stance"].items()}
    if mtype != "opinion":
        stance = "en_contra"
    elif len(stance_hits["a_favor"]) > len(stance_hits["en_contra"]):
        stance = "a_favor"
    elif stance_hits["en_contra"]:
        stance = "en_contra"
    else:
        stance = "neutral"
    topic = detect_topic(text, ctx.get("topics") or [])
    level = (ctx.get("alert") or {}).get("level") or "bajo"
    rank = ALERT_RANK.get(level, 0)
    texts = rules["recommendation_text"]
    canalizar = mtype == "queja_ciudadana_legitima"
    if canalizar:
        rec, why = "responder", texts["responder_queja"]
    elif mtype == "acusacion_o_difamacion":
        rec, why = ("responder", texts["responder_acusacion"]) if rank >= 2 else ("monitorear", texts["monitorear_acusacion"])
    elif mtype in ("dato_falso", "dato_sacado_de_contexto"):
        rec, why = ("responder", texts["responder_dato"]) if rank >= 1 else ("monitorear", texts["monitorear_dato_bajo"])
    elif stance == "a_favor":
        rec, why = ("responder", texts["responder_favor"]) if rank >= 1 else ("monitorear", texts["monitorear_favor"])
    elif stance == "en_contra":
        rec, why = ("responder", texts["responder_opinion_alta"]) if rank >= 2 else ("monitorear", texts["monitorear_opinion"]) if rank == 1 else ("ignorar", texts["ignorar_opinion"])
    else:
        rec, why = "monitorear", texts["monitorear_neutral"]
    evidence = sorted({*type_hits, *stance_hits.get(stance, [])})
    confidence = min(0.95, 0.55 + 0.1 * len(evidence))
    level_label = {"sin_linea_base": "sin línea base"}.get(level, f"alerta {level}")
    explanation = why.format(level=level_label)
    if evidence:
        explanation += f" Señales: {', '.join(evidence[:4])}."
    return {"stance": stance, "topic": topic, "message_type": mtype, "recommendation": rec, "confidence": round(confidence, 2), "explanation": explanation, "canalizar_a_atencion": canalizar}
