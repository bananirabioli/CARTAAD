"""9.1 Numeric data: every number, percentage, amount and date must match a cited fact (value, unit, period)."""

from datetime import date
from typing import Any

from app.models.kb import Fact
from app.services.facts import is_expired
from app.validators.common import Finding, finding
from app.validators.context import PieceContext, fact_years
from app.validators.numbers import Figure, extract_figures, same_value, units_compatible

V = "numeric"


def _fact_dates(fact: Fact) -> set[date]:
    out = {d.date() for d in (fact.period_start, fact.period_end, fact.fact_date) if d}
    out |= {f.day for f in extract_figures(fact.statement) if f.kind == "date" and f.day}
    return out


def figure_matches(fig: Figure, fact: Fact) -> bool:
    if fig.kind in ("number", "percent", "money"):
        if fact.value is not None and same_value(fig.value, fact.value) and units_compatible(fig.unit, fact.unit):
            return True
        # secondary figures quoted verbatim from the cited fact's own statement (e.g. «en menos de 48 horas»)
        return any(same_value(fig.value, other.value) and units_compatible(fig.unit, other.unit) for other in extract_figures(fact.statement) if other.kind in ("number", "percent", "money"))
    if fig.kind == "year":
        return int(fig.value or 0) in fact_years(fact)
    if fig.kind == "date":
        return fig.day in _fact_dates(fact) if fig.day else int(fig.value or 0) in fact_years(fact)
    return False


def _period_days(f: Fact) -> int | None:
    return (f.period_end - f.period_start).days if f.period_start and f.period_end else None


def _comparison_findings(ctx: PieceContext) -> list[Finding]:
    comp = (ctx.piece.content or {}).get("comparison") or {}
    left = [ctx.facts[i] for i in comp.get("left") or [] if i in ctx.facts]
    right = [ctx.facts[i] for i in comp.get("right") or [] if i in ctx.facts]
    if not left or not right:
        return []
    mode = comp.get("mode") or ("comparativa" if ctx.piece.format_slug == "formato_comparativa" else "antes_despues")
    out = []
    for a in left:
        for b in right:
            same_base = (a.base or "").strip().lower() == (b.base or "").strip().lower() and units_compatible(a.unit, b.unit)
            if mode == "antes_despues":
                da, db_ = _period_days(a), _period_days(b)
                same_period = da is not None and db_ is not None and abs(da - db_) <= max(3, 0.1 * max(da, db_))
            else:
                same_period = (a.period_start, a.period_end) == (b.period_start, b.period_end) and a.period_start is not None
            if not (same_base and same_period):
                out.append(finding(V, "comparison_mismatch", "block", detail={"left": a.code, "right": b.code, "mode": mode}, left=a.code, right=b.code))
    return out


def validate_numeric(ctx: PieceContext) -> tuple[list[Finding], list[dict[str, Any]]]:
    """Returns (findings, figure records for FigureCheck)."""
    findings: list[Finding] = []
    figures: list[dict[str, Any]] = []
    modes = ctx.settings.validator_modes
    for unit in ctx.units():
        if unit.quoted or not unit.text:
            continue
        cited = [ctx.facts[i] for i in unit.fact_ids if i in ctx.facts]
        for fid in unit.fact_ids:
            if fid not in ctx.facts:
                findings.append(finding(V, "fact_missing", "block", rule_id="HR-08", detail={"fact_id": fid, "location": unit.location}, fact_id=fid, location=unit.location))
        for fig in extract_figures(unit.text):
            match = next((f for f in cited if figure_matches(fig, f)), None)
            figures.append({"raw": fig.raw, "kind": fig.kind, "value": fig.value, "unit": fig.unit, "location": unit.location, "fact_id": match.id if match else None, "matched": match is not None})
            if not cited:
                findings.append(finding(V, "unsourced", "block", rule_id="HR-01", detail={"raw": fig.raw, "location": unit.location}, raw=fig.raw, location=unit.location))
            elif match is None:
                expected = ", ".join(f"{f.code}={f.value:g} {f.unit}".strip() if f.value is not None else f.code for f in cited)
                findings.append(finding(V, "mismatch", "block", rule_id="HR-01", detail={"raw": fig.raw, "location": unit.location, "expected": expected}, raw=fig.raw, location=unit.location, expected=expected))
    for fact in ctx.facts.values():
        if fact.id not in ctx.cited_fact_ids():
            continue
        if is_expired(fact, ctx.now):
            sev = "block" if modes.fact_expired == "block" else "warn"
            findings.append(finding(V, "fact_expired", sev, detail={"fact": fact.code}, fact=fact.code, until=fact.valid_until.date().isoformat() if fact.valid_until else ""))
        if fact.document_id is None:
            sev = "block" if modes.fact_without_document == "block" else "warn"
            findings.append(finding(V, "fact_no_document", sev, rule_id="HR-01", detail={"fact": fact.code}, fact=fact.code))
    findings += _comparison_findings(ctx)
    return findings, figures
