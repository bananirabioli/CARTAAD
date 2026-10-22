"""check_directive (mock): lexical detection of opposite instructions between free-text directives."""

import re
from typing import Any

from app.textnorm import normalize

_REQUIRE = re.compile(r"\b(siempre|usar|incluir|mencionar|destacar|priorizar|enfatizar|decir)\b\s+(?:el |la |los |las |que )?(?:termino |palabra |frase )?[«\"']?([a-zñ ]{4,40}?)[»\"']?(?:[.,;]|$| en | al | cuando )")
_AVOID = re.compile(r"\b(nunca|evitar|no usar|no mencionar|no decir|no incluir|prohibido|omitir)\b\s+(?:el |la |los |las |que )?(?:termino |palabra |frase )?[«\"']?([a-zñ ]{4,40}?)[»\"']?(?:[.,;]|$| en | al | cuando )")


def _phrases(rx: re.Pattern[str], text: str) -> set[str]:
    return {m.group(2).strip() for m in rx.finditer(normalize(text)) if len(m.group(2).strip()) >= 4}


def check_directive(ctx: dict[str, Any]) -> dict[str, Any]:
    target = ctx["directive"]
    t_text = f"{target.get('title', '')}. {target.get('text', '')}"
    t_req, t_avoid = _phrases(_REQUIRE, t_text), _phrases(_AVOID, t_text)
    conflicts = []
    for other in ctx.get("others", []):
        o_text = f"{other.get('title', '')}. {other.get('text', '')}"
        o_req, o_avoid = _phrases(_REQUIRE, o_text), _phrases(_AVOID, o_text)
        clash = {p for p in t_req for q in o_avoid if p in q or q in p} | {p for p in t_avoid for q in o_req if p in q or q in p}
        if clash:
            term = sorted(clash)[0]
            conflicts.append(
                {
                    "directive_code": other["code"],
                    "explanation": f"Una pide usar «{term}» y la otra pide evitarlo, en texto libre (detección sugerida).",
                    "severity": "advertencia",
                }
            )
    return {"conflicts": conflicts}
