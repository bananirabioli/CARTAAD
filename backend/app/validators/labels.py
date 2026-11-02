"""9.5 Mandatory labels and image rules: «ilustración representativa» (HR-07), consent for real testimonies (HR-07),
generated-image metadata and real photos as the only evidence (HR-06), visible sources (HR-01)."""

from app.guardrails.hard_rules import REPRESENTATIVE_LABEL, rule_enabled
from app.services.client_settings import rules_dict
from app.textnorm import find_terms
from app.validators.common import Finding, finding
from app.validators.context import PieceContext

V = "labels"
EVIDENCE_FORMATS = {"formato_comparativa", "formato_clasico"}


def validate_labels(ctx: PieceContext) -> list[Finding]:
    out: list[Finding] = []
    p = ctx.piece
    content = p.content or {}
    if p.kind != "creative":
        return out
    text_only = bool(ctx.creative and ctx.creative.text_only)
    if ctx.fmt and (ctx.fmt.options or {}).get("illustrated_figures") and not text_only and rule_enabled(rules_dict(ctx.settings), "HR-07L"):
        if not find_terms(content.get("label") or "", [REPRESENTATIVE_LABEL]):
            out.append(finding(V, "representative_label", "block", rule_id="HR-07"))
    if ctx.creative and ctx.creative.requires_consent:
        if ctx.consent is None:
            out.append(finding(V, "consent_missing", "warn", rule_id="HR-07"))
        if not ((content.get("slots") or {}).get("cita") or {}).get("text"):
            out.append(finding(V, "testimony_missing", "warn", rule_id="HR-07"))
    for img in content.get("images") or []:
        meta = img.get("meta") or {}
        if img.get("generated"):
            if not (meta.get("generada_por_ia") and meta.get("ilustracion")):
                out.append(finding(V, "generated_meta", "block", rule_id="HR-06"))
            if ctx.creative and (ctx.creative.requires_real_photo or ctx.creative.is_comparison):
                out.append(finding(V, "generated_as_evidence", "block", rule_id="HR-06"))
        elif img.get("approved_image_id"):
            ai = ctx.images.get(img["approved_image_id"])
            evidence = (ctx.creative and (ctx.creative.requires_real_photo or ctx.creative.is_comparison)) or p.format_slug in EVIDENCE_FORMATS
            if ai is None:
                out.append(finding(V, "image_missing", "block", image=img["approved_image_id"]))
            elif evidence and (ai.image_type != "foto_real" or not ai.credit.strip() or not ai.approved):
                out.append(finding(V, "evidence_not_real", "block", rule_id="HR-06", image=ai.title))
    cited = sorted({ctx.facts[i].code for i in ctx.cited_fact_ids() if i in ctx.facts})
    footer = " ".join(content.get("sources") or [])
    missing = [code for code in cited if code not in footer]
    if missing and not text_only:
        out.append(finding(V, "sources_missing", "block", rule_id="HR-01", detail={"missing": missing}, facts=", ".join(missing)))
    return out
