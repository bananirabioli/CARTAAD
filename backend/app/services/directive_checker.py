"""Directive conflict verification (6.10): hard rules, other directives, modo veda and style limits.

Deterministic checks decide; the LLM step `check_directive` only adds findings marked as AI-suggested that a person
confirms or dismisses.
"""

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.runner import StepMeta, run_step
from app.db import utcnow
from app.guardrails.hard_rules import check_text_against_hard_rules
from app.i18n import t
from app.models.styles import Directive, Style
from app.services.style_resolver import (
    LEVEL_NAMES,
    LEVEL_STYLE,
    directive_level,
    scopes_overlap,
    struct_list,
    terms_clash,
    windows_overlap,
)
from app.services.veda import overlapping_restrictions

SEVERITY_ORDER = {"rechazada_por_regla_dura": 4, "conflicto_bloqueante": 3, "advertencia": 2, "resuelto_por_prioridad": 1, "sin_conflicto": 0}


def _fid(*parts: Any) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _text_of(d: Directive) -> list[str]:
    structured = d.structured or {}
    values = [d.title, d.text]
    for value in structured.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values += [v for v in value if isinstance(v, str)]
    return values


def _resolution(a: Directive, b: Directive) -> tuple[str, str]:
    la, lb = directive_level(a), directive_level(b)
    if la != lb:
        winner = a if la < lb else b
        return "resuelto_por_prioridad", t("directives.check.wins_by_level", code=winner.code, level=LEVEL_NAMES[min(la, lb)])
    if a.priority != b.priority:
        winner = a if a.priority > b.priority else b
        return "resuelto_por_prioridad", t("directives.check.wins_by_priority", code=winner.code, priority=winner.priority)
    return "conflicto_bloqueante", t("directives.check.tie", a=a.code, b=b.code, priority=a.priority)


def _vs_directives(d: Directive, others: list[Directive]) -> list[dict[str, Any]]:
    out = []
    for o in others:
        if not scopes_overlap(d.scope, o.scope) or not windows_overlap(d.valid_from, d.valid_until, o.valid_from, o.valid_until):
            continue
        pairs = [(req, pro, d.code, o.code) for req in struct_list(d, "vocabulario_obligatorio") for pro in struct_list(o, "vocabulario_prohibido")]
        pairs += [(req, pro, o.code, d.code) for req in struct_list(o, "vocabulario_obligatorio") for pro in struct_list(d, "vocabulario_prohibido")]
        for req, pro, req_code, pro_code in pairs:
            if terms_clash(req, pro):
                status, resolution = _resolution(d, o)
                out.append(
                    {
                        "id": _fid("dir", o.code, req, pro), "kind": "directiva", "other": o.code, "ai_suggested": False,
                        "severity": "bloqueante" if status == "conflicto_bloqueante" else "resuelto",
                        "explanation": t("directives.check.vocab_clash", req_code=req_code, term=req, pro_code=pro_code, pro=pro),
                        "resolution": resolution,
                    }
                )
        d_max, o_req = (d.structured or {}).get("intensidad_maxima"), (o.structured or {}).get("intensidad_requerida")
        o_max, d_req = (o.structured or {}).get("intensidad_maxima"), (d.structured or {}).get("intensidad_requerida")
        for mx, rq, mx_code, rq_code in ((d_max, o_req, d.code, o.code), (o_max, d_req, o.code, d.code)):
            if isinstance(mx, int) and isinstance(rq, int) and rq > mx:
                status, resolution = _resolution(d, o)
                out.append(
                    {
                        "id": _fid("int", o.code, mx, rq), "kind": "directiva", "other": o.code, "ai_suggested": False,
                        "severity": "bloqueante" if status == "conflicto_bloqueante" else "resuelto",
                        "explanation": t("directives.check.intensity_clash", rq_code=rq_code, rq=rq, mx_code=mx_code, mx=mx),
                        "resolution": resolution,
                    }
                )
    return out


def _vs_veda(db: Session, d: Directive) -> list[dict[str, Any]]:
    out = []
    for r in overlapping_restrictions(db, d.client_id, d.valid_from, d.valid_until):
        formats = set((d.scope or {}).get("formats") or []) & set(r.blocked_formats or [])
        creatives = set(struct_list(d, "creativos")) & set(r.blocked_creatives or [])
        legend_hits = [lg for lg in r.mandatory_legends or [] for pro in struct_list(d, "vocabulario_prohibido") if terms_clash(pro, lg)]
        if formats or creatives or legend_hits:
            what = ", ".join(sorted(formats | creatives)) or ", ".join(legend_hits)
            when = f"{r.starts_at:%d/%m/%Y}–{r.ends_at:%d/%m/%Y}" if r.starts_at and r.ends_at else ""
            out.append(
                {
                    "id": _fid("veda", r.id, what), "kind": "veda", "other": r.name, "ai_suggested": False, "severity": "advertencia",
                    "explanation": t("directives.check.veda_clash", name=r.name, what=what, when=when),
                    "resolution": t("directives.check.veda_wins"),
                }
            )
    return out


def _vs_styles(db: Session, d: Directive) -> list[dict[str, Any]]:
    out = []
    scoped = (d.scope or {}).get("styles") or []
    stmt = select(Style).where(Style.client_id == d.client_id, Style.status == "activo")
    styles = [s for s in db.scalars(stmt) if not scoped or s.slug in scoped]
    req_i = (d.structured or {}).get("intensidad_requerida")
    for s in styles:
        if isinstance(req_i, int) and not (s.intensity_min <= req_i <= s.intensity_max) and (scoped or s.intensity_max < req_i):
            out.append(
                {
                    "id": _fid("style_int", s.slug, req_i), "kind": "estilo", "other": s.slug, "ai_suggested": False, "severity": "bloqueante",
                    "explanation": t("directives.check.style_intensity", value=req_i, style=s.slug, min=s.intensity_min, max=s.intensity_max),
                    "resolution": t("directives.check.style_intensity_fix"),
                }
            )
        for req in struct_list(d, "vocabulario_obligatorio"):
            for pro in s.prohibited_vocab or []:
                if terms_clash(req, pro):
                    lvl = directive_level(d)
                    winner = d.code if lvl < LEVEL_STYLE else f"estilo:{s.slug}"
                    out.append(
                        {
                            "id": _fid("style_vocab", s.slug, req), "kind": "estilo", "other": s.slug, "ai_suggested": False, "severity": "resuelto",
                            "explanation": t("directives.check.style_vocab", term=req, style=s.slug),
                            "resolution": t("directives.check.wins_generic", code=winner),
                        }
                    )
    return out


def _ai_findings(db: Session, d: Directive, others: list[Directive], previous: list[dict[str, Any]], user_id: int | None) -> list[dict[str, Any]]:
    context = {
        "directive": {"code": d.code, "title": d.title, "text": d.text, "structured": d.structured, "scope": d.scope},
        "others": [{"code": o.code, "title": o.title, "text": o.text} for o in others],
    }
    result, _ = run_step(db, "check_directive", context, StepMeta(client_id=d.client_id, user_id=user_id))
    decisions = {f["id"]: f.get("confirmed") for f in previous if f.get("ai_suggested")}
    out = []
    for c in result.conflicts:  # type: ignore[attr-defined]
        fid = _fid("ai", c.directive_code, c.explanation)
        confirmed = decisions.get(fid)
        if confirmed is False:
            continue
        out.append(
            {
                "id": fid, "kind": "ia", "other": c.directive_code, "ai_suggested": True, "confirmed": confirmed,
                "severity": "bloqueante" if confirmed and c.severity == "bloqueante" else "advertencia",
                "explanation": c.explanation, "resolution": t("directives.check.ai_needs_human"),
            }
        )
    return out


def check_directive(db: Session, d: Directive, *, use_ai: bool = True, user_id: int | None = None) -> dict[str, Any]:
    hard = [m.as_dict() for m in check_text_against_hard_rules(*_text_of(d))]
    others = [
        o
        for o in db.scalars(select(Directive).where(Directive.client_id == d.client_id, Directive.status.in_(("activa", "en_revision", "borrador"))))
        if o.code != d.code
    ]
    findings: list[dict[str, Any]] = []
    if not hard:
        findings += _vs_directives(d, others)
        findings += _vs_veda(db, d)
        findings += _vs_styles(db, d)
        if use_ai and d.text:
            findings += _ai_findings(db, d, others, (d.conflict_report or {}).get("findings", []), user_id)

    if hard:
        status = "rechazada_por_regla_dura"
    elif any(f["severity"] == "bloqueante" for f in findings):
        status = "conflicto_bloqueante"
    elif any(f["severity"] == "advertencia" for f in findings):
        status = "advertencia"
    elif findings:
        status = "resuelto_por_prioridad"
    else:
        status = "sin_conflicto"
    report = {"status": status, "checked_at": utcnow().isoformat(), "hard_rules": hard, "findings": findings}
    d.conflict_status = status
    d.conflict_report = report
    if hard:
        d.status = "rechazada"
        d.rejection_reason = "; ".join(f"{h['rule_id']}: {h['message']}" for h in hard)
    return report


def can_activate(d: Directive) -> tuple[bool, str]:
    if d.conflict_status == "rechazada_por_regla_dura":
        return False, t("directives.errors.hard_rule")
    if d.conflict_status == "conflicto_bloqueante":
        return False, t("directives.errors.blocking")
    return True, ""
