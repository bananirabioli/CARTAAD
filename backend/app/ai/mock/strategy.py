"""recommend_strategy (mock): mapping candidates + verdicts + learning context."""

from typing import Any

LABEL = {"desmentir": "desmentir", "contextualizar": "contextualizar", "reencuadrar": "reencuadrar", "contrastar": "contrastar", "amplificar": "amplificar", "agradecer": "agradecer"}


def recommend_strategy(ctx: dict[str, Any]) -> dict[str, Any]:
    candidates = ctx.get("candidates") or ["contextualizar"]
    learning = ctx.get("learning") or {}
    claims = ctx.get("claims") or []
    verdicts = [c.get("verdict") for c in claims]
    by_strategy = {g["value"]: g for g in learning.get("strategies", [])}
    learned = [by_strategy[c] for c in candidates if c in by_strategy and by_strategy[c]["sufficient"]]
    learned.sort(key=lambda g: g["rate"], reverse=True)
    if learned and learned[0]["rate"] >= 0.5:
        choice = learned[0]["value"]
        why_learning = f" En este tema, «{choice}» funcionó {learned[0]['ok']} de {learned[0]['n']} veces."
    else:
        choice = candidates[0]
        n = learning.get("sample_size", 0)
        why_learning = f" Muestra histórica insuficiente ({n} casos) para usar el aprendizaje como argumento." if n < learning.get("min_sample", 5) else ""
    mtype = (ctx.get("classification") or {}).get("message_type", "opinion")
    reasons = {
        "desmentir": f"Hay {verdicts.count('falsa')} afirmación(es) falsa(s) contradichas por hechos de la base.",
        "contextualizar": f"El dato existe pero le falta contexto ({verdicts.count('incompleta')} afirmación(es) incompleta(s)) o se debe informar qué se hará.",
        "reencuadrar": "Conviene mover la conversación hacia lo verificable sin repetir el señalamiento.",
        "contrastar": "Hay datos comparables con la misma base y el mismo periodo.",
        "amplificar": "La publicación es favorable y se puede reforzar con datos.",
        "agradecer": "Reconocer a quien publicó fortalece la relación con la ciudadanía.",
    }
    if mtype == "acusacion_o_difamacion":
        reasons["reencuadrar"] += " Es una acusación: no se repite la acusación y legal revisa antes."
    if choice == "desmentir" and "falsa" not in verdicts and "contextualizar" in candidates:
        choice = "contextualizar"
    justification = reasons.get(choice, "Estrategia del mapeo configurado.") + why_learning
    alternatives = [{"strategy": c, "why": reasons.get(c, "")} for c in candidates if c != choice]
    return {"strategy": choice, "justification": justification, "alternatives": alternatives}
