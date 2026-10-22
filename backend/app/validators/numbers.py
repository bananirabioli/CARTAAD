"""Figure extraction for es-MX text: numbers, percentages, amounts, years and dates.

Conventions (es-MX): comma = thousands separator, dot = decimal ("1,247.5"). Multipliers "mil", "millones",
"mil millones". Codes like "H-001" or "D-012" and list markers ("1. ") are not figures.
"""

import re
from dataclasses import dataclass
from datetime import date

from app.textnorm import normalize

MONTHS = {m: i for i, m in enumerate(["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"], start=1)}
MONTH_RX = "|".join(MONTHS)

UNIT_SYNONYMS = {
    "%": ["%", "por ciento", "porciento"],
    "pesos": ["pesos", "mdp", "mxn", "$"],
    "km": ["km", "kilometros", "kms"],
    "horas": ["horas", "hora", "hrs", "h"],
    "minutos": ["minutos", "minuto", "min"],
    "dias": ["dias", "dia"],
}
_UNIT_LOOKUP = {normalize(v): k for k, vals in UNIT_SYNONYMS.items() for v in vals}
_STOP_UNITS = {"de", "del", "la", "el", "los", "las", "en", "y", "a", "al", "por", "que", "se", "para", "con"}

_DATE = re.compile(rf"\b(\d{{1,2}}) de ({MONTH_RX})(?: de(?:l)? (\d{{4}}))?\b")
_MONTH_YEAR = re.compile(rf"\b({MONTH_RX}) (?:de(?:l)? )?(\d{{4}})\b")
_NUM = re.compile(
    r"(?<![\w.,\-/])(\$\s?)?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"(\s*(?:mil millones|millones|millon|mil))?"
    r"(\s*(?:%|por ?ciento))?"
)
_LIST_MARKER = re.compile(r"(?:^|\n)\s*\d{1,2}[.)]\s")


@dataclass
class Figure:
    raw: str
    kind: str  # number | percent | money | year | date
    value: float | None = None
    unit: str | None = None
    day: date | None = None
    start: int = 0

    def as_dict(self) -> dict:
        return {"raw": self.raw, "kind": self.kind, "value": self.value, "unit": self.unit, "date": self.day.isoformat() if self.day else None}


def normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    u = normalize(unit).strip()
    if u in _UNIT_LOOKUP:
        return _UNIT_LOOKUP[u]
    if u.startswith("millones de pesos") or u.startswith("pesos"):
        return "pesos"
    return u.rstrip("s") if len(u) > 3 else u


def units_compatible(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    na, nb = normalize_unit(a), normalize_unit(b)
    return na == nb or (na or "").startswith(nb or "~") or (nb or "").startswith(na or "~")


def extract_figures(text: str) -> list[Figure]:
    norm = normalize(text)
    figures: list[Figure] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in taken)

    for m in _DATE.finditer(norm):
        day, month, year = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
        if 1 <= day <= 31:
            d = date(int(year), month, min(day, 28) if month == 2 and day > 28 else day) if year else None
            figures.append(Figure(m.group(0), "date", value=float(year) if year else None, day=d, start=m.start()))
            taken.append(m.span())
    for m in _MONTH_YEAR.finditer(norm):
        if free(*m.span()):
            figures.append(Figure(m.group(0), "year", value=float(m.group(2)), day=date(int(m.group(2)), MONTHS[m.group(1)], 1), start=m.start()))
            taken.append(m.span())
    markers = {mm.end() - 3 for mm in _LIST_MARKER.finditer(norm)}
    for m in _NUM.finditer(norm):
        if not free(*m.span()) or any(abs(m.start() - x) <= 2 for x in markers):
            continue
        dollar, integer, decimals, mult, pct = m.groups()
        value = float(integer.replace(",", "") + (f".{decimals}" if decimals else ""))
        multiplier = (mult or "").strip()
        if multiplier == "mil millones":
            value *= 1_000_000_000
        elif multiplier in ("millones", "millon"):
            value *= 1_000_000
        elif multiplier == "mil":
            value *= 1_000
        tail = norm[m.end() : m.end() + 40]
        unit = None
        if pct:
            kind, unit = "percent", "%"
        elif dollar or re.match(r"\s*(?:de )?pesos\b", tail):
            kind, unit = "money", "pesos"
        elif not decimals and not multiplier and 1900 <= value <= 2100 and "," not in integer:
            kind = "year"
        else:
            kind = "number"
            word = re.match(r"\s*([a-zñ%]+)", tail)
            if word and word.group(1) not in _STOP_UNITS:
                unit = normalize_unit(word.group(1))
        figures.append(Figure(m.group(0).strip(), kind, value=value, unit=unit, start=m.start()))
        taken.append(m.span())
    figures.sort(key=lambda f: f.start)
    return figures


def same_value(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= max(1e-9, abs(b) * 1e-6)
