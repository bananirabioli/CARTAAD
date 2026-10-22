"""9.3 Style compliance linter (deterministic)."""

import re

from app.services.style_resolver import LEVEL_SUGGESTED, ResolvedStyle
from app.textnorm import find_terms
from app.validators.common import Finding, finding, status_of

_EMOJI = re.compile("[\U0001f300-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff]")
_CAPS_WORD = re.compile(r"\b[A-ZÁÉÍÓÚÑÜ]{4,}\b")
_ALLOWED_ACRONYMS = {"ALERTA", "CONTEXTO", "DATO", "FALSO", "CEA", "PAZ", "PVL", "LED"}


def lint(text: str, resolved: ResolvedStyle, *, piece_kind: str = "copy", length_key: str = "copy_principal") -> tuple[str, list[Finding]]:
    findings: list[Finding] = []
    style = resolved.style

    for rule in resolved.prohibited:
        hit = find_terms(text, [rule.term])
        if hit:
            severity = "warn" if rule.level >= LEVEL_SUGGESTED else "block"
            findings.append(finding("style", "prohibited_term", severity, detail={"term": rule.term, "source": rule.source, "snippet": hit[0].snippet}, term=rule.term, source=rule.source))

    if piece_kind == "copy":
        for term in resolved.mandatory_terms:
            if not find_terms(text, [term]):
                findings.append(finding("style", "mandatory_missing", "warn", detail={"term": term}, term=term))
        limits = (style.length or {}).get(length_key) or {}
        n = len(text)
        if limits.get("max") and n > int(limits["max"]) * 1.15:
            findings.append(finding("style", "too_long", "warn", detail={"length": n, **limits}, length=n, max=limits["max"]))
        if limits.get("min") and n < int(limits["min"]) * 0.7:
            findings.append(finding("style", "too_short", "warn", detail={"length": n, **limits}, length=n, min=limits["min"]))

    if style.emoji_usage == "ninguno" and _EMOJI.search(text):
        findings.append(finding("style", "emoji", "warn"))
    caps = [w for w in _CAPS_WORD.findall(text) if w not in _ALLOWED_ACRONYMS]
    if caps and (len(caps) >= 2 or style.caps_usage == "normal"):
        findings.append(finding("style", "caps", "warn", detail={"words": caps[:5]}, words=", ".join(caps[:5])))

    for legend in resolved.legend_texts:
        if not find_terms(text, [legend]):
            findings.append(finding("style", "legend_missing", "block", rule_id="HR-04" if legend in [lg["text"] for lg in resolved.legends if lg["source"] == "veda"] else None, detail={"legend": legend}, legend=legend))

    return status_of(findings), findings
