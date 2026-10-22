"""9.4 Compatibility: creative × format matrix, style allowed for the target format, modo veda and registered accounts."""

from app.guardrails.hard_rules import restriction_active
from app.services.catalog import style_allowed_for_format
from app.validators.common import Finding, finding
from app.validators.context import PieceContext

V = "compat"


def validate_compat(ctx: PieceContext) -> list[Finding]:
    out: list[Finding] = []
    p = ctx.piece
    if p.creative_slug and ctx.compat_level == "none":
        out.append(finding(V, "matrix_none", "block", detail={"creative": p.creative_slug, "format": p.format_slug}, creative=p.creative_slug, format=p.format_slug, note=ctx.compat_note))
    if p.creative_slug and ctx.compat_level == "partial" and not (p.adaptation or "").strip():
        out.append(finding(V, "adaptation_missing", "warn", creative=p.creative_slug))
    if ctx.style and ctx.fmt and not style_allowed_for_format(ctx.style, ctx.fmt):
        out.append(finding(V, "style_not_allowed", "block", style=ctx.style.slug, format=ctx.fmt.slug))
    if ctx.veda and restriction_active(ctx.veda, ctx.now):
        if p.format_slug in (ctx.veda.blocked_formats or []):
            out.append(finding(V, "veda_format", "block", rule_id="HR-04", format=p.format_slug, name=ctx.veda.name))
        if p.creative_slug and p.creative_slug in (ctx.veda.blocked_creatives or []):
            out.append(finding(V, "veda_creative", "block", rule_id="HR-04", creative=p.creative_slug, name=ctx.veda.name))
    if ctx.account is not None and not (ctx.account.registered and ctx.account.verified):
        out.append(finding(V, "unregistered_account", "block", rule_id="HR-02"))
    return out
