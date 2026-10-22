"""StyleResolver: combines a style with the applicable directives and the modo veda, with explicit precedence.

Precedence (highest first, 6.10):
  1 reglas duras > 2 modo veda > 3 directrices linea_roja > 4 directrices obligatorias > 5 guía del estilo
  > 6 directrices sugeridas > 7 ajustes puntuales (caso / copiloto)
Lower levels never override higher ones. Within a level the higher priority wins; a tie is an unresolved conflict
(the prohibition is kept, which is the conservative choice).
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import utcnow
from app.guardrails.hard_rules import required_legends
from app.i18n import t
from app.models.ops import RestrictionMode
from app.models.styles import Directive, Style
from app.services.veda import active_restriction
from app.textnorm import normalize

LEVEL_HARD, LEVEL_VEDA, LEVEL_RED_LINE, LEVEL_MANDATORY, LEVEL_STYLE, LEVEL_SUGGESTED, LEVEL_ADJUST = 1, 2, 3, 4, 5, 6, 7
LEVEL_NAMES = {1: "regla_dura", 2: "modo_veda", 3: "linea_roja", 4: "obligatoria", 5: "estilo", 6: "sugerida", 7: "ajuste"}
SCOPE_KEYS = ("topics", "formats", "accounts", "styles", "flows")


def directive_level(d: Directive) -> int:
    if d.dtype == "linea_roja":
        return LEVEL_RED_LINE
    return LEVEL_MANDATORY if d.mandatory == "obligatoria" else LEVEL_SUGGESTED


def struct_list(d: Directive, key: str) -> list[str]:
    value = (d.structured or {}).get(key) or []
    return [v for v in value if isinstance(v, str) and v.strip()] if isinstance(value, list) else []


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", normalize(text)).split())


def terms_clash(a: str, b: str) -> bool:
    na, nb = _words(a), _words(b)
    return bool(na and nb) and (na == nb or f" {na} " in f" {nb} " or f" {nb} " in f" {na} ")


def scope_matches(scope: dict[str, Any] | None, values: dict[str, Any]) -> bool:
    for key in SCOPE_KEYS:
        allowed = [str(v) for v in (scope or {}).get(key) or []]
        value = values.get(key)
        # A scoped directive applies only when the context names a matching value.
        if allowed and (value is None or str(value) not in allowed):
            return False
    return True


def scopes_overlap(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    for key in SCOPE_KEYS:
        la, lb = {str(v) for v in (a or {}).get(key) or []}, {str(v) for v in (b or {}).get(key) or []}
        if la and lb and not la & lb:
            return False
    return True


def windows_overlap(a_start: datetime | None, a_end: datetime | None, b_start: datetime | None, b_end: datetime | None) -> bool:
    return (a_end is None or b_start is None or b_start <= a_end) and (a_start is None or b_end is None or a_start <= b_end)


def directive_in_force(d: Directive, when: datetime) -> bool:
    return d.status == "activa" and (d.valid_from is None or d.valid_from <= when) and (d.valid_until is None or when <= d.valid_until)


@dataclass
class VocabRule:
    term: str
    kind: str  # prohibit | require
    level: int
    priority: int
    source: str  # D-012 | estilo:cercano
    active: bool = True
    note: str = ""


@dataclass
class AppliedDirective:
    id: int
    code: str
    version: int
    dtype: str
    title: str
    text: str
    level: int
    mandatory: str
    priority: int
    effect: str = "aplicada"  # aplicada | parcial | conflicto
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "code": self.code, "version": self.version, "dtype": self.dtype, "title": self.title,
            "level": LEVEL_NAMES[self.level], "mandatory": self.mandatory, "priority": self.priority, "effect": self.effect, "notes": self.notes,
        }


@dataclass
class ResolvedStyle:
    style: Style
    applied: list[AppliedDirective]
    vocab: list[VocabRule]
    legends: list[dict[str, str]]
    intensity_min: int
    intensity_max: int
    intensity_target: int
    conflicts: list[dict[str, Any]]
    topic_priorities: list[str]
    veda: RestrictionMode | None
    adjustments: dict[str, Any]

    @property
    def prohibited(self) -> list[VocabRule]:
        return [v for v in self.vocab if v.kind == "prohibit" and v.active]

    @property
    def prohibited_terms(self) -> list[str]:
        return [v.term for v in self.prohibited]

    @property
    def mandatory_terms(self) -> list[str]:
        return [v.term for v in self.vocab if v.kind == "require" and v.active and v.level in (LEVEL_RED_LINE, LEVEL_MANDATORY)]

    @property
    def legend_texts(self) -> list[str]:
        return [lg["text"] for lg in self.legends]

    def trace(self) -> list[dict[str, Any]]:
        return [a.as_dict() for a in self.applied]

    def style_tags(self) -> list[str]:
        tags = [f"{dim}:{v}" for dim, values in (self.style.tags or {}).items() for v in values]
        return [*tags, *(self.style.free_tags or [])]

    def summary(self) -> dict[str, Any]:
        return {
            "style": {"id": self.style.id, "slug": self.style.slug, "name": self.style.name, "version": self.style.version},
            "intensity": [self.intensity_min, self.intensity_max, self.intensity_target],
            "prohibited": [{"term": v.term, "source": v.source, "level": LEVEL_NAMES[v.level]} for v in self.prohibited],
            "mandatory": self.mandatory_terms,
            "legends": self.legends,
            "applied_directives": self.trace(),
            "conflicts": self.conflicts,
            "veda": {"id": self.veda.id, "name": self.veda.name} if self.veda else None,
        }

    def style_block(self) -> str:
        s = self.style
        tags = s.tags or {}
        tag_line = " · ".join(f"{t('styles.dimension.' + dim)}={','.join(vals)}" for dim, vals in tags.items() if vals)
        voice = s.voice or {}
        length = (s.length or {}).get("copy_principal") or {}
        lines = [
            f"ESTILO: {s.slug} (v{s.version})",
            f"Etiquetas: {tag_line} · intensidad={self.intensity_min}-{self.intensity_max}",
            f"Voz: {voice.get('persona', '').replace('_', ' ')}, {voice.get('trato', '')}, {voice.get('idioma', 'es-MX')}",
            "Haz: " + "; ".join((s.guidelines or {}).get("haz", [])),
            "Evita: " + "; ".join((s.guidelines or {}).get("evita", [])),
            "Vocabulario prohibido: " + (", ".join(self.prohibited_terms) or "ninguno"),
            "Vocabulario preferido: " + (", ".join(s.preferred_vocab or []) or "ninguno"),
            f"Longitud: copy principal {length.get('min', '?')}–{length.get('max', '?')} caracteres; emoji: {s.emoji_usage}; mayúsculas: {s.caps_usage}",
            f"Intensidad objetivo: {self.intensity_target}",
            "DIRECTRICES APLICADAS (por precedencia):",
        ]
        if self.veda:
            for lg in self.legends:
                if lg["source"] == "veda":
                    lines.append(f"[MODO VEDA] Leyenda obligatoria (la agrega el sistema): {lg['text']}")
        for a in self.applied:
            if a.effect == "conflicto":
                continue
            lines.append(f"[{a.code} {a.dtype}] {a.title}: {a.text}".strip())
        if self.adjustments:
            lines.append(f"[AJUSTES DEL CASO] {self.adjustments}")
        return "\n".join(lines)


def applicable_directives(db: Session, client_id: int, values: dict[str, Any], when: datetime) -> list[Directive]:
    rows = db.scalars(select(Directive).where(Directive.client_id == client_id, Directive.status == "activa"))
    out = [d for d in rows if directive_in_force(d, when) and scope_matches(d.scope, values)]
    out.sort(key=lambda d: (directive_level(d), -d.priority, d.code))
    return out


def resolve(
    db: Session,
    client_id: int,
    style: Style,
    *,
    topic: str | None = None,
    format_slug: str | None = None,
    account_id: int | None = None,
    flow: str | None = None,
    adjustments: dict[str, Any] | None = None,
    when: datetime | None = None,
) -> ResolvedStyle:
    when = when or utcnow()
    adjustments = dict(adjustments or {})
    values = {"topics": topic, "formats": format_slug, "accounts": account_id, "styles": style.slug, "flows": flow}
    directives = applicable_directives(db, client_id, values, when)
    veda = active_restriction(db, client_id, when)

    vocab: list[VocabRule] = [VocabRule(term, "prohibit", LEVEL_STYLE, 0, f"estilo:{style.slug}") for term in style.prohibited_vocab or []]
    legends: list[dict[str, str]] = [{"text": text, "source": "veda"} for text in required_legends(veda, when)]
    applied: list[AppliedDirective] = []
    conflicts: list[dict[str, Any]] = []
    imin, imax = style.intensity_min, style.intensity_max
    target = imin
    topic_priorities: list[str] = []

    for d in directives:
        level = directive_level(d)
        entry = AppliedDirective(d.id, d.code, d.version, d.dtype, d.title, d.text, level, d.mandatory, d.priority)
        applied.append(entry)
        vocab += [VocabRule(term, "prohibit", level, d.priority, d.code) for term in struct_list(d, "vocabulario_prohibido")]
        vocab += [VocabRule(term, "require", level, d.priority, d.code) for term in struct_list(d, "vocabulario_obligatorio")]
        legend = (d.structured or {}).get("leyenda_texto")
        if legend and level <= LEVEL_MANDATORY:
            legends.append({"text": legend, "source": d.code})
        topic_priorities += struct_list(d, "temas_prioritarios")
        max_i = (d.structured or {}).get("intensidad_maxima")
        if isinstance(max_i, int) and level <= LEVEL_MANDATORY:
            if max_i >= style.intensity_min:
                imax = min(imax, max_i)
            else:
                entry.effect = "conflicto"
                entry.notes.append(t("styles.resolver.max_below_style", value=max_i, style_min=style.intensity_min))
        req_i = (d.structured or {}).get("intensidad_requerida")
        if isinstance(req_i, int):
            if style.intensity_min <= req_i <= style.intensity_max:
                target = max(target, req_i)
            else:
                entry.effect = "conflicto"
                entry.notes.append(t("styles.resolver.intensity_out_of_style", value=req_i, min=style.intensity_min, max=style.intensity_max))
                conflicts.append({"a": d.code, "b": f"estilo:{style.slug}", "explanation": entry.notes[-1]})

    # Veda legends beat any prohibition that would remove them.
    for rule in vocab:
        if rule.kind == "prohibit" and any(terms_clash(rule.term, lg["text"]) for lg in legends if lg["source"] == "veda"):
            rule.active, rule.note = False, t("styles.resolver.overridden_by_veda")

    # Prohibit vs require between sources.
    for p in [v for v in vocab if v.kind == "prohibit"]:
        for r in [v for v in vocab if v.kind == "require"]:
            if not (p.active and r.active) or not terms_clash(p.term, r.term):
                continue
            if p.level != r.level:
                loser, winner = (r, p) if p.level < r.level else (p, r)
            elif p.priority != r.priority:
                loser, winner = (r, p) if p.priority > r.priority else (p, r)
            else:
                r.active = False
                r.note = t("styles.resolver.tie", a=p.source, b=r.source, term=p.term)
                conflicts.append({"a": p.source, "b": r.source, "term": p.term, "explanation": r.note, "unresolved": True})
                _mark(applied, (p.source, r.source), "conflicto", r.note)
                continue
            loser.active = False
            loser.note = t("styles.resolver.overridden", term=loser.term, winner=winner.source, level=LEVEL_NAMES[winner.level])
            _mark(applied, (loser.source,), "parcial", loser.note)

    # Level 7: case / copilot adjustments move inside the (already narrowed) style range, never outside.
    if "intensity" in adjustments:
        requested = int(adjustments["intensity"])
        target = max(imin, min(requested, imax))
        if requested != target:
            adjustments["intensity_clamped"] = target
    target = max(imin, min(target, imax))

    return ResolvedStyle(
        style=style, applied=applied, vocab=vocab, legends=legends, intensity_min=imin, intensity_max=imax, intensity_target=target,
        conflicts=conflicts, topic_priorities=topic_priorities, veda=veda, adjustments=adjustments,
    )


def _mark(applied: list[AppliedDirective], codes: tuple[str, ...], effect: str, note: str) -> None:
    for a in applied:
        if a.code in codes:
            if a.effect != "conflicto":
                a.effect = effect
            a.notes.append(note)
