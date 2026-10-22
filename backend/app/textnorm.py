"""Text normalization shared by guardrails and validators.

Matching must survive case changes, different accents, zero-width characters, letter spacing
("c o r r u p t o", "c.o.r.r.u.p.t.o") and simple leetspeak ("c0rrupt0").
"""

import re
import unicodedata
from dataclasses import dataclass

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
_SPACED_LETTERS = re.compile(r"\b(?:[a-zñ][\s.\-_*·]){2,}[a-zñ]\b")
_MIXED_TOKEN = re.compile(r"\b(?=\w*[a-z])(?=\w*\d)[\w@$]+\b")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Lowercase, accent-free, zero-width-free, whitespace-collapsed."""
    text = (text or "").translate(_ZERO_WIDTH)
    text = strip_accents(text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def deobfuscate(text: str) -> str:
    """normalize() plus collapsing of spaced letters and leetspeak inside mixed tokens."""
    norm = normalize(text)
    norm = _SPACED_LETTERS.sub(lambda m: re.sub(r"[\s.\-_*·]", "", m.group(0)), norm)
    return _MIXED_TOKEN.sub(lambda m: m.group(0).translate(_LEET), norm)


@dataclass(frozen=True)
class TermMatch:
    term: str
    snippet: str


def find_terms(text: str, terms: list[str]) -> list[TermMatch]:
    """Find each term (word-boundary, normalized) in text, resisting obfuscation."""
    if not text or not terms:
        return []
    variants = {normalize(text), deobfuscate(text)}
    found: list[TermMatch] = []
    seen: set[str] = set()
    for term in terms:
        nterm = normalize(term)
        if not nterm or nterm in seen:
            continue
        pattern = re.compile(r"(?<!\w)" + re.escape(nterm).replace(r"\ ", r"\s+") + r"(?!\w)")
        for variant in variants:
            m = pattern.search(variant)
            if m:
                start, end = max(0, m.start() - 30), min(len(variant), m.end() + 30)
                found.append(TermMatch(term=term, snippet=variant[start:end]))
                seen.add(nterm)
                break
    return found


def contains_term(text: str, term: str) -> bool:
    return bool(find_terms(text, [term]))


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?¡¿…])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]
