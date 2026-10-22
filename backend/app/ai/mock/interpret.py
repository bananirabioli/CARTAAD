"""interpret (mock): claim extraction and verdicts against the facts in context; comment themes; missing context."""

import re
from typing import Any

from app.ai.mock.fixtures import mock_json
from app.textnorm import normalize, sentences
from app.validators.numbers import extract_figures, same_value, units_compatible

ABSOLUTE = re.compile(r"\b(ni un|ni una|cero|nunca|nada|no existe|no ha|no han|abandonad\w*|se disparo|no tiene ni)\b|100%")
ACCUSATION = ("corrup", "roban", "fraude", "coludid", "desvio", "encubre", "nido de")
CONTEXT_WORDS = ("solo", "apenas", "mientras que", "nomas", "unicamente", "la mitad")
STOP = {"de", "la", "el", "en", "los", "las", "y", "que", "un", "una", "del", "por", "con", "se", "para", "al", "es", "lo", "su", "sus", "no", "ni", "a"}


def _words(text: str) -> set[str]:
    """Crude stems (first 5 letters) so «bache» matches «baches»."""
    return {w[:5] for w in re.findall(r"[a-zñ]+", normalize(text)) if w not in STOP and len(w) > 3}


def _usable(f: dict[str, Any]) -> bool:
    return not f.get("expired") and f.get("has_document", True)


def _overlap(a: str, b: str) -> int:
    return len(_words(a) & _words(b))


def _best_related(claim: str, facts: list[dict[str, Any]], exclude: set[int], need_value: bool = True) -> dict[str, Any] | None:
    pool = [f for f in facts if _usable(f) and f["id"] not in exclude and (f.get("value") is not None or not need_value)]
    pool.sort(key=lambda f: (f.get("topic") is not None, _overlap(claim, f["statement"])), reverse=True)
    return pool[0] if pool else None


def _judge(sentence: str, facts: list[dict[str, Any]], mtype: str) -> dict[str, Any] | None:
    norm = normalize(sentence)
    figures = [f for f in extract_figures(sentence) if f.kind in ("number", "percent", "money")]
    is_absolute = bool(ABSOLUTE.search(norm)) and (mtype == "dato_falso" or bool(figures))
    is_accusation = any(w in norm for w in ACCUSATION)
    is_context = any(w in norm for w in CONTEXT_WORDS)
    if is_accusation:
        return {
            "text": sentence, "verdict": "no_verificable", "fact_ids": [],
            "explanation": "Acusación sin hechos en la base que la respalden o la desmientan; requiere revisión de legal antes de cualquier respuesta pública.",
            "missing_data": "Información oficial verificable sobre el señalamiento (pedir al dueño de la base y a legal).",
        }
    for fig in figures:
        if fig.unit == "%" and fig.value == 100 and is_absolute:
            break
        exact = [f for f in facts if _usable(f) and same_value(f.get("value"), fig.value) and units_compatible(f.get("unit"), fig.unit)]
        if exact:
            fact = exact[0]
            if is_context or mtype == "dato_sacado_de_contexto":
                extra = _best_related(sentence, facts, {fact["id"]})
                ids = [fact["id"]] + ([extra["id"]] if extra else [])
                omitted = f" Omite que {extra['statement'][0].lower()}{extra['statement'][1:]}" if extra else ""
                return {"text": sentence, "verdict": "incompleta", "fact_ids": ids, "explanation": f"La cifra es correcta ({fact['code']}), pero se presenta sin contexto.{omitted}", "missing_data": None}
            return {"text": sentence, "verdict": "cierta", "fact_ids": [fact["id"]], "explanation": f"Coincide con {fact['code']}: {fact['statement']}", "missing_data": None}
        same_unit = [f for f in facts if _usable(f) and f.get("value") is not None and fig.unit and units_compatible(f.get("unit"), fig.unit)]
        if same_unit:
            fact = max(same_unit, key=lambda f: (f.get("topic") is not None, _overlap(sentence, f["statement"])))
            return {"text": sentence, "verdict": "falsa", "fact_ids": [fact["id"]], "explanation": f"La cifra no coincide con el registro oficial: {fact['statement']}", "missing_data": None}
    if is_absolute:
        fact = _best_related(sentence, facts, set())
        if fact:
            return {"text": sentence, "verdict": "falsa", "fact_ids": [fact["id"]], "explanation": f"Afirmación absoluta contradicha por {fact['code']}: {fact['statement']}", "missing_data": None}
        return {"text": sentence, "verdict": "no_verificable", "fact_ids": [], "explanation": "No hay hechos en la base para verificarla.", "missing_data": "Cifra oficial sobre el tema: pedir al dueño de la base."}
    if figures:
        return {"text": sentence, "verdict": "no_verificable", "fact_ids": [], "explanation": "La cifra no aparece en la base de conocimiento.", "missing_data": f"Dato oficial equivalente a «{figures[0].raw}»: pedir al dueño de la base."}
    return None


def _themes(comments: list[str]) -> list[dict[str, Any]]:
    rules = mock_json("classify_rules").get("comment_themes", [])
    if not comments:
        return []
    counts: dict[str, list[str]] = {}
    for c in comments:
        norm = normalize(c)
        for rule in rules:
            if any(normalize(w) in norm for w in rule["any"]):
                counts.setdefault(rule["theme"], []).append(c)
                break
        else:
            counts.setdefault("otros", []).append(c)
    labels = {r["theme"]: r["label"] for r in rules} | {"otros": "Otros comentarios"}
    out = []
    for theme, items in sorted(counts.items(), key=lambda kv: len(kv[1]), reverse=True):
        example = items[0][:90]
        out.append({"theme": labels.get(theme, theme), "share": round(len(items) / len(comments), 2), "summary": f"{len(items)} comentario(s); por ejemplo: «{example}»."})
    return out


def interpret(ctx: dict[str, Any]) -> dict[str, Any]:
    post = ctx.get("post") or {}
    cls = ctx.get("classification") or {}
    mtype = cls.get("message_type", "opinion")
    facts = ctx.get("facts") or []
    claims = [c for c in (_judge(s, facts, mtype) for s in sentences(post.get("text", ""))) if c]
    missing: list[dict[str, Any]] = []
    for c in claims:
        if c["verdict"] == "incompleta":
            missing.append({"description": f"Contexto omitido: {c['explanation']}", "needs_kb_owner": False})
        if c.get("missing_data"):
            missing.append({"description": f"Dato faltante: {c['missing_data']}", "needs_kb_owner": True})
    for comp in ctx.get("competences") or []:
        missing.append({"description": f"Competencia ({comp['level']}): {comp['description']}", "needs_kb_owner": False})
    if not any(_usable(f) for f in facts):
        missing.append({"description": f"Dato faltante: no hay hechos vigentes sobre «{cls.get('topic', 'el tema')}»; pedir al dueño de la base.", "needs_kb_owner": True})
    verdicts = [c["verdict"] for c in claims]
    counts = ", ".join(f"{verdicts.count(v)} {v.replace('_', ' ')}" for v in ("falsa", "incompleta", "cierta", "no_verificable") if v in verdicts) or "sin afirmaciones verificables"
    stance = {"en_contra": "crítica", "a_favor": "favorable", "neutral": "neutral"}.get(cls.get("stance", ""), "")
    summary = f"Publicación {stance} sobre {cls.get('topic', 'el tema')}: «{post.get('text', '')[:160]}». Afirmaciones: {counts}."
    narrative = {
        "dato_falso": "Narrativa de abandono basada en una cifra o afirmación absoluta que contradicen los registros.",
        "dato_sacado_de_contexto": "Narrativa construida con un dato real presentado sin su contexto.",
        "acusacion_o_difamacion": "Señalamiento de conducta ilícita sin respaldo verificable en la base.",
        "queja_ciudadana_legitima": "Queja ciudadana concreta y legítima; requiere atención, no confrontación.",
        "opinion": "Opinión sobre la gestión; no contiene datos verificables específicos." if stance != "favorable" else "Reconocimiento ciudadano a una acción concreta.",
    }.get(mtype, "")
    return {"summary": summary, "narrative": narrative, "claims": claims, "missing_context": missing[:8], "comments_summary": _themes(ctx.get("comments") or [])}
