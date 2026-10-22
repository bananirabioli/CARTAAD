"""Deterministic copy composer used by the MockProvider (generate_copy and copilot rewrites).

It only uses facts present in the context and cites their ids, like the real model must.
"""

from typing import Any

from app.ai.mock.fixtures import fixture_for_style
from app.textnorm import find_terms

FLOW_DEFAULT_STRATEGY = {"A": "contextualizar", "B": "amplificar"}


def _lower_first(text: str) -> str:
    if not text:
        return text
    words = text.split(" ", 1)
    # Keep proper nouns ("Municipio Ejemplo", "Gobierno Estatal…") capitalized; lowercase articles only.
    if words[0] in ("El", "La", "Los", "Las", "Se", "En", "Entre", "Un", "Una"):
        return words[0].lower() + (" " + words[1] if len(words) > 1 else "")
    return text


def _fmt(template: str, ctx: dict[str, Any], **extra: Any) -> str:
    values = {
        "topic": ctx.get("topic_name") or "este tema",
        "client": ctx.get("client_name") or "El equipo",
        "closing": ctx.get("closing_phrase") or "Mismo periodo, misma base.",
        **extra,
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError):
        return template


def _pick(options: list[str] | str | None, index: int) -> str:
    if not options:
        return ""
    if isinstance(options, str):
        return options
    return options[max(0, min(index, len(options) - 1))]


def _cycle(options: list[str] | str | None, index: int) -> str:
    if not options:
        return ""
    if isinstance(options, str):
        return options
    return options[index % len(options)]


def fact_sentence(fx: dict[str, Any], fact: dict[str, Any], index: int, ctx: dict[str, Any]) -> str:
    prefix = _cycle(fx.get("fact_prefix"), index)
    issuer = fact.get("issuer") or "la fuente oficial"
    statement = fact["statement"].strip()
    if prefix:
        prefix = _fmt(prefix, ctx, issuer=issuer)
        statement = _lower_first(statement) if prefix.rstrip().endswith((",", ":")) else statement
    return f"{prefix}{statement}"


def compose_copy(ctx: dict[str, Any]) -> dict[str, Any]:
    style = ctx.get("style") or {}
    slug = style.get("slug", "institucional")
    fixture_slug, fx = fixture_for_style(slug, style.get("tags"))
    flow = ctx.get("flow") or "A"
    strategy = ctx.get("strategy") or FLOW_DEFAULT_STRATEGY.get(flow, "contextualizar")
    imin, imax = int(style.get("intensity_min", 1)), int(style.get("intensity_max", 2))
    intensity = max(imin, min(int(ctx.get("intensity") or imin), imax))
    level = intensity - 1
    variant = int(ctx.get("variant") or 0)
    claims = ctx.get("claims") or []
    has_false = any(c.get("verdict") == "falsa" for c in claims)
    prohibited = [p for p in ctx.get("prohibited_vocab") or []]

    segments: list[dict[str, Any]] = []
    if ctx.get("complaint") or ctx.get("empathy_first"):
        segments.append({"text": _fmt(fx.get("empathy", ""), ctx), "type": "opinion_marcada", "fact_ids": []})

    if strategy == "desmentir" and has_false and fx.get("false_opener"):
        opener = _fmt(fx["false_opener"], ctx)
    else:
        opener = _fmt(_pick(fx.get("openers", {}).get(strategy) or fx.get("openers", {}).get(FLOW_DEFAULT_STRATEGY[flow]), level + variant), ctx)
    segments.append({"text": opener, "type": "opinion_marcada", "fact_ids": []})

    facts = list(ctx.get("facts") or [])
    max_len_hint = ((style.get("length") or {}).get("copy_principal") or {}).get("max") or 400
    max_facts = 1 if int(max_len_hint) < 280 else int(ctx.get("max_facts") or 2)
    used = facts[:max_facts]
    missing: list[str] = []
    for i, fact in enumerate(used):
        segments.append({"text": fact_sentence(fx, fact, i + variant, ctx), "type": "asercion_factual", "fact_ids": [fact["id"]]})
    if not used:
        segments.append({"text": _fmt(fx.get("no_fact", ""), ctx), "type": "opinion_marcada", "fact_ids": []})
        missing.append(f"Dato oficial sobre {ctx.get('topic_name') or 'el tema'}: pedir al dueño de la base.")

    for phrase in ctx.get("mandatory_vocab") or []:
        segments.append({"text": _fmt(fx.get("mandatory_template", "{phrase}."), ctx, phrase=phrase), "type": "opinion_marcada", "fact_ids": [], "_keep": True})
    if not ctx.get("mandatory_vocab") and ctx.get("key_messages"):
        km = ctx["key_messages"][variant % len(ctx["key_messages"])]
        segments.append({"text": km, "type": "opinion_marcada", "fact_ids": []})

    closer = _fmt((fx.get("closers") or {}).get(flow, ""), ctx)
    if closer:
        segments.append({"text": closer, "type": "llamado", "fact_ids": []})

    # Respect the resolved prohibited vocabulary: drop non-factual segments that contain a banned term.
    if prohibited:
        segments = [s for s in segments if s["type"] == "asercion_factual" or not find_terms(s["text"], prohibited)]

    max_len = ((style.get("length") or {}).get("copy_principal") or {}).get("max")
    if max_len:
        while sum(len(s["text"]) + 1 for s in segments) > max_len and len(segments) > 2:
            removable = [i for i, s in enumerate(segments) if s["type"] in ("opinion_marcada", "llamado") and i > 0 and not s.get("_keep")]
            if not removable:
                break
            segments.pop(removable[-1])

    for seg in segments:
        seg.pop("_keep", None)
    why = f"Estilo {style.get('name', slug)} (fixture «{fixture_slug}»), estrategia «{strategy}», intensidad {intensity}; {len(used)} hecho(s) citado(s) de la base."
    return {"segments": segments, "why": why, "adaptation": None, "missing_data": missing}
