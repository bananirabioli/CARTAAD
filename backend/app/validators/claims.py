"""9.2 Claims about actors (HR-08): factual assertions need valid facts; attributions to actors outside factual
segments are flagged as possible unbacked claims."""

import re

from app.services.actors import mentioned_actors
from app.services.facts import is_expired
from app.textnorm import normalize
from app.validators.common import Finding, finding
from app.validators.context import PieceContext

V = "claims"


def _attribution(text: str, verbs: list[str]) -> str | None:
    norm = f" {normalize(text)} "
    for verb in verbs:
        if re.search(rf"\b{re.escape(normalize(verb))}\b", norm):
            return verb
    return None


def validate_claims(ctx: PieceContext) -> list[Finding]:
    findings: list[Finding] = []
    verbs = ctx.settings.attribution_verbs
    mode = "block" if ctx.settings.validator_modes.unbacked_actor_mention == "block" else "warn"
    for unit in ctx.units():
        if unit.quoted or not unit.text:
            continue
        if unit.seg_type == "asercion_factual":
            valid = [i for i in unit.fact_ids if i in ctx.facts and not is_expired(ctx.facts[i], ctx.now)]
            if not unit.fact_ids or len(valid) != len(unit.fact_ids):
                findings.append(finding(V, "factual_unbacked", "block", rule_id="HR-08", detail={"location": unit.location, "text": unit.text[:140]}, location=unit.location))
            continue
        if unit.fact_ids:  # creative slots with cited facts are covered by the numeric validator
            continue
        actors = mentioned_actors(ctx.actors, unit.text)
        verb = _attribution(unit.text, verbs) if actors else None
        if actors and verb:
            findings.append(
                finding(V, "actor_attribution", mode, rule_id="HR-08", detail={"location": unit.location, "actor": actors[0].name, "verb": verb}, actor=actors[0].name, verb=verb, location=unit.location)
            )
    return findings
