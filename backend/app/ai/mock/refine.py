"""refine_piece (mock): deterministic copilot rewrites. Limits (intensity, register) are checked in code before this runs."""

import re
from copy import deepcopy
from typing import Any

from app.ai.mock.compose import _fmt, _pick, compose_copy, fact_sentence
from app.ai.mock.creatives import generate_creatives
from app.ai.mock.fixtures import fixture_for_style, style_fixtures
from app.textnorm import normalize

REGISTER_FIXTURE = {"formal": "institucional", "cotidiano": "cercano", "coloquial": "voz_ciudadana_representativa"}


def _opener(ctx: dict[str, Any], fx: dict[str, Any]) -> str:
    level = max(0, int(ctx.get("target_intensity") or 1) - 1)
    return _fmt(_pick((fx.get("openers") or {}).get(ctx.get("strategy") or "contextualizar"), level + int(ctx.get("variant") or 0)), ctx)


def _replace_opener(segments: list[dict[str, Any]], text: str) -> list[dict[str, Any]]:
    out = deepcopy(segments)
    for seg in out:
        if seg["type"] in ("opinion_marcada", "saludo"):
            seg["text"] = text
            return out
    return [{"text": text, "type": "opinion_marcada", "fact_ids": []}, *out]


def _shorten_copy(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keep: list[dict[str, Any]] = []
    first_opinion = False
    for seg in segments:
        if seg["type"] == "asercion_factual" and sum(1 for s in keep if s["type"] == "asercion_factual") < 1:
            keep.append(seg)
        elif seg["type"] in ("opinion_marcada", "saludo") and not first_opinion:
            keep.append(seg)
            first_opinion = True
        elif seg["type"] == "llamado" and not any(s["type"] == "llamado" for s in keep):
            keep.append(seg)
    return keep if len(keep) < len(segments) else segments[: max(1, len(segments) - 1)]


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return m.group(1) if m else text


def _free(instruction: str, piece: dict[str, Any], ctx: dict[str, Any], fx: dict[str, Any]) -> tuple[dict[str, Any], str]:
    norm = normalize(instruction)
    content = deepcopy(piece["content"])
    segs = content.get("segments")
    m = re.search(r"(?:reemplaza|cambia)\s+[«\"'](.+?)[»\"']\s+por\s+[«\"'](.+?)[»\"']", instruction, re.IGNORECASE)
    if m:
        old, new = m.group(1), m.group(2)
        if segs is not None:
            for s in segs:
                s["text"] = s["text"].replace(old, new)
        for s in content.get("slots", {}).values() if isinstance(content.get("slots"), dict) else []:
            s["text"] = s.get("text", "").replace(old, new)
        return content, f"Reemplazado «{old}» por «{new}»."
    m = re.search(r"(?:quita|elimina|borra)\s+[«\"'](.+?)[»\"']", instruction, re.IGNORECASE)
    if m and segs is not None:
        term = normalize(m.group(1))
        content["segments"] = [s for s in segs if term not in normalize(s["text"])]
        return content, f"Se quitó el segmento que mencionaba «{m.group(1)}»."
    if "pregunta" in norm and segs is not None:
        q = _fmt(fx.get("question") or "", ctx)
        if q:
            content["segments"] = [*segs, {"text": q, "type": "pregunta", "fact_ids": []}]
            return content, "Se agregó una pregunta de cierre."
    if any(w in norm for w in ("corto", "breve", "resume", "sintetiza")) and segs is not None:
        content["segments"] = _shorten_copy(segs)
        return content, "Versión más breve."
    if segs is not None:
        content["segments"] = _replace_opener(segs, _opener({**ctx, "variant": int(ctx.get("variant") or 0) + 1}, fx))
    return content, "Instrucción aplicada en modo mock: se reformuló la apertura (sin lectura semántica de la instrucción)."


def refine_piece(ctx: dict[str, Any]) -> dict[str, Any]:
    piece = ctx["piece"]
    action = ctx.get("action", "libre")
    style = ctx.get("style") or {}
    _, fx = fixture_for_style(style.get("slug", "institucional"), style.get("tags"))
    is_copy = piece.get("kind") == "copy"
    content = deepcopy(piece["content"])
    note = ""

    if action == "cambiar_estilo" or action == "otro_angulo" or (not is_copy and action in ("mas_firme", "mas_formal", "menos_formal", "mas_empatico")):
        if is_copy:
            out = compose_copy({**ctx, "intensity": ctx.get("target_intensity"), "empathy_first": action == "mas_empatico"})
            content["segments"] = out["segments"]
        else:
            regenerated = generate_creatives({**ctx, "intensity": ctx.get("target_intensity"), "creatives": [ctx["creative"]]})["creatives"][0]
            content["slots"] = {s["name"]: {"text": s["text"], "fact_ids": s["fact_ids"]} for s in regenerated["slots"]}
            content["slides"] = regenerated["slides"]
        note = {"cambiar_estilo": f"Reescrita en el estilo «{style.get('name', style.get('slug'))}».", "otro_angulo": f"Nuevo ángulo: estrategia «{ctx.get('strategy')}»."}.get(action, "Ajuste aplicado.")
    elif action == "mas_corto":
        if is_copy:
            content["segments"] = _shorten_copy(content["segments"])
        else:
            if content.get("slides"):
                content["slides"] = content["slides"][: max(3 if piece.get("text_only") else 5, len(content["slides"]) - 1)]
            for slot in (content.get("slots") or {}).values():
                if not slot.get("fact_ids"):
                    slot["text"] = _first_sentence(slot.get("text", ""))
        note = "Versión más corta."
    elif action in ("mas_firme", "mas_empatico", "mas_formal", "menos_formal"):
        target_fx = fx
        if action in ("mas_formal", "menos_formal") and ctx.get("register_target"):
            target_fx = style_fixtures().get(REGISTER_FIXTURE.get(ctx["register_target"], ""), fx)
        opener = _opener(ctx, target_fx)
        segs = _replace_opener(content["segments"], opener)
        if action == "mas_empatico" and not any(normalize(s["text"]) == normalize(_fmt(fx.get("empathy", ""), ctx)) for s in segs):
            segs = [{"text": _fmt(fx.get("empathy", ""), ctx), "type": "opinion_marcada", "fact_ids": []}, *segs]
        content["segments"] = segs
        note = {"mas_firme": "Apertura más firme, dentro del máximo del estilo.", "mas_empatico": "Se reconoce primero la preocupación.", "mas_formal": "Registro más formal.", "menos_formal": "Registro más cotidiano."}[action]
    elif action == "agregar_dato":
        fact = ctx.get("add_fact")
        if not fact:
            return {"refused": True, "refusal_reason": "Dato faltante: no hay un hecho vigente y pertinente en la base; pídelo al dueño de la base.", "note": ""}
        sentence = fact_sentence(fx, fact, 1, ctx)
        if is_copy:
            segs = content["segments"]
            idx = max((i for i, s in enumerate(segs) if s["type"] == "asercion_factual"), default=0)
            content["segments"] = [*segs[: idx + 1], {"text": sentence, "type": "asercion_factual", "fact_ids": [fact["id"]]}, *segs[idx + 1 :]]
        elif content.get("slides") is not None and content.get("slides"):
            content["slides"].insert(-1, {"title": "Un dato más", "text": sentence, "fact_ids": [fact["id"]]})
        else:
            content.setdefault("slots", {})["dato_extra"] = {"text": sentence, "fact_ids": [fact["id"]]}
        note = f"Se agregó el dato {fact['code']} con su fuente."
    else:
        content, note = _free(ctx.get("instruction") or "", piece, ctx, fx)

    result: dict[str, Any] = {"refused": False, "note": note}
    if is_copy:
        result["segments"] = content.get("segments", [])
    else:
        result["slots"] = [{"name": k, "text": v.get("text", ""), "fact_ids": v.get("fact_ids", [])} for k, v in (content.get("slots") or {}).items()]
        result["slides"] = content.get("slides") or []
    return result
