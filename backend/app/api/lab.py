"""Laboratorio: per-client models, creative guides and rules, OpenRouter model catalog and prompt preview.

Everything is stored in Client.settings (ClientSettings) and every change goes to the audit log, which is also the
history the Laboratorio shows.
"""

import time
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.ai.prompts import load_prompt
from app.ai.runner import layer_for
from app.api.deps import Ctx, get_ctx, require
from app.config import get_settings
from app.errors import AppError
from app.guardrails.hard_rules import LOCKED_RULES, SWITCHES, effective_rules, hard_rules_prompt_block
from app.models.core import AuditLog
from app.models.ops import AiRun
from app.services import audit
from app.services.client_settings import AI_LAYERS, get_client_settings, rules_dict, update_client_settings

router = APIRouter(prefix="/lab", tags=["lab"])

Layer = Literal["analysis", "text", "image", "video"]
_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
CACHE_SECONDS = 3600


def _price(p: dict[str, Any] | None, key: str, per: float = 1_000_000) -> float | None:
    try:
        v = float((p or {}).get(key) or 0)
    except (TypeError, ValueError):
        return None
    return round(v * per, 4) if v else None


def _fetch(kind: str) -> list[dict[str, Any]]:
    base = get_settings().openrouter_base_url
    if kind == "video":
        data = httpx.get(f"{base}/videos/models", timeout=30).json().get("data", [])
        out = []
        for m in data:
            skus = m.get("pricing_skus") or {}
            cents = next((v for k, v in skus.items() if "720p" in k), None) or next(iter(skus.values()), None)
            out.append({"id": m["id"], "name": m.get("name", m["id"]), "price": f"{float(cents) / 100:.3f} USD/s" if cents else None,
                        "notes": f"duraciones {m.get('supported_durations')} · {', '.join(m.get('supported_aspect_ratios') or [])}"})
        return out
    params = {"output_modalities": "image"} if kind == "image" else {}
    data = httpx.get(f"{base}/models", params=params, timeout=30).json().get("data", [])
    out = []
    for m in data:
        arch = m.get("architecture") or {}
        ins, outs = arch.get("input_modalities") or [], arch.get("output_modalities") or []
        params_ = m.get("supported_parameters") or []
        if kind == "image":
            if "image" not in outs:
                continue
            price = _price(m.get("pricing"), "image", 1) or _price(m.get("pricing"), "completion")
            note = "solo imagen" if "text" not in outs else "imagen + texto"
            out.append({"id": m["id"], "name": m.get("name", m["id"]), "price": f"{price} USD/img" if price and price < 5 else (f"{price} USD/M tok" if price else None), "notes": note})
            continue
        if "text" not in outs or "image" in outs:
            continue
        if kind == "analysis" and "image" not in ins:
            continue
        structured = "structured_outputs" in params_ or "response_format" in params_
        pin, pout = _price(m.get("pricing"), "prompt"), _price(m.get("pricing"), "completion")
        out.append({"id": m["id"], "name": m.get("name", m["id"]), "price": f"{pin} / {pout} USD por M tok" if pin is not None else None,
                    "notes": ("JSON estricto" if structured else "sin JSON estricto (se pide en el prompt)") + f" · contexto {m.get('context_length') or '?'}",
                    "structured": structured})
    out.sort(key=lambda r: (not r.get("structured", True), r["id"]))
    return out


@router.get("/models", response_model=list[dict[str, Any]])
def list_models(kind: Layer = Query(...), refresh: bool = False, ctx: Ctx = Depends(get_ctx)) -> list[dict[str, Any]]:
    """OpenRouter catalog filtered for one layer (vision for analysis, text, image output, video). Cached one hour."""
    cached = _CACHE.get(kind)
    if cached and not refresh and time.time() - cached[0] < CACHE_SECONDS:
        return cached[1]
    try:
        rows = _fetch(kind)
    except (httpx.HTTPError, ValueError) as exc:
        if cached:
            return cached[1]
        raise AppError(502, "ai_error", f"No se pudo leer el catálogo de OpenRouter: {exc.__class__.__name__}") from exc
    _CACHE[kind] = (time.time(), rows)
    return rows


def _env_models() -> dict[str, str]:
    s = get_settings()
    return {"analysis": s.openrouter_model_analysis, "text": s.openrouter_model_text, "image": s.openrouter_model_image, "video": s.openrouter_model_video}


@router.get("/config", response_model=dict[str, Any])
def get_config(ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    s = get_settings()
    cs = get_client_settings(ctx.client)
    env = _env_models()
    chosen = cs.ai_models.model_dump()
    return {
        "providers": {"llm": s.llm_provider, "image": s.image_provider, "video": s.video_provider}, "key_present": bool(s.openrouter_api_key),
        "models": {layer: {"default": env[layer], "client": chosen.get(layer), "effective": chosen.get(layer) or env[layer]} for layer in AI_LAYERS},
        "guides": cs.ai_guides.model_dump(), "rules": effective_rules(rules_dict(cs)), "facts_top_k": cs.facts_top_k,
        "video_seconds": s.video_max_seconds, "locked": sorted(LOCKED_RULES), "switches": list(SWITCHES),
    }


class ModelsIn(BaseModel):
    models: dict[Layer, str | None]


class GuidesIn(BaseModel):
    guides: dict[Layer, str] = Field(default_factory=dict)
    facts_top_k: int | None = Field(default=None, ge=1, le=25)


class RuleIn(BaseModel):
    enabled: bool = True
    text: str | None = Field(default=None, max_length=1500)


class RulesIn(BaseModel):
    rules: dict[str, RuleIn]


def _save(ctx: Ctx, action: str, patch: dict[str, Any], note: str) -> dict[str, Any]:
    before = get_client_settings(ctx.client).model_dump()
    try:
        updated = update_client_settings(ctx.client, patch)
    except ValueError as exc:
        raise AppError(422, "invalid_value", detail=str(exc)) from exc
    keys = list(patch)
    audit.record(ctx.db, action=action, entity_type="client_settings", entity_id=ctx.client_id, client_id=ctx.client_id, user=ctx.user,
                 before={k: before.get(k) for k in keys}, after={k: updated.model_dump().get(k) for k in keys}, note=note)
    ctx.db.commit()
    return get_config(ctx)


@router.put("/models", response_model=dict[str, Any])
def set_models(body: ModelsIn, ctx: Ctx = Depends(require("config.manage"))) -> dict[str, Any]:
    clean = {k: (v.strip() or None) if isinstance(v, str) else None for k, v in body.models.items()}
    return _save(ctx, "lab.models", {"ai_models": clean}, ", ".join(f"{k}={v or 'default'}" for k, v in clean.items()))


@router.put("/guides", response_model=dict[str, Any])
def set_guides(body: GuidesIn, ctx: Ctx = Depends(require("config.manage"))) -> dict[str, Any]:
    patch: dict[str, Any] = {"ai_guides": {k: v.strip() for k, v in body.guides.items()}}
    if body.facts_top_k is not None:
        patch["facts_top_k"] = body.facts_top_k
    return _save(ctx, "lab.guides", patch, ", ".join(body.guides) or "top-k")


@router.put("/rules", response_model=dict[str, Any])
def set_rules(body: RulesIn, ctx: Ctx = Depends(require("config.manage"))) -> dict[str, Any]:
    current = rules_dict(get_client_settings(ctx.client))
    for rule_id, cfg in body.rules.items():
        current[rule_id] = {"enabled": cfg.enabled, "text": (cfg.text or "").strip() or None}
    return _save(ctx, "lab.rules", {"rules": current}, ", ".join(f"{k}:{'on' if v.enabled else 'off'}" for k, v in body.rules.items()))


@router.get("/history", response_model=list[dict[str, Any]])
def history(ctx: Ctx = Depends(get_ctx), limit: int = Query(30, ge=1, le=200)) -> list[dict[str, Any]]:
    rows = ctx.db.scalars(select(AuditLog).where(AuditLog.client_id == ctx.client_id, AuditLog.action.like("lab.%")).order_by(AuditLog.id.desc()).limit(limit))
    return [{"id": a.id, "at": a.created_at.isoformat(), "who": a.user_label, "action": a.action, "note": a.note, "before": a.before, "after": a.after} for a in rows]


class PreviewIn(BaseModel):
    step: Literal["analyze_capture", "generate_content"]
    case_id: int | None = None


@router.post("/preview", response_model=dict[str, Any])
def preview(body: PreviewIn, ctx: Ctx = Depends(get_ctx)) -> dict[str, Any]:
    """Re-render the latest real run of this step (for the case, or the client) with today's template, guides and rules.
    No AI call: it shows exactly what the next run would send."""
    stmt = select(AiRun).where(AiRun.client_id == ctx.client_id, AiRun.step == body.step)
    if body.case_id:
        stmt = stmt.where(AiRun.case_id == body.case_id)
    run = ctx.db.scalar(stmt.order_by(AiRun.id.desc()).limit(1))
    if run is None or not isinstance((run.input or {}).get("context"), dict):
        raise AppError(404, "not_found", "Aún no hay una corrida de este paso para usarla como ejemplo: captura o genera una vez.")
    cs = get_client_settings(ctx.client)
    context = dict(run.input["context"])
    context.setdefault("guides", cs.ai_guides.model_dump())
    context["guides"] = cs.ai_guides.model_dump()
    context.setdefault("engagement_read", None)
    context.setdefault("analyst_context", "")
    prompt = load_prompt(body.step)
    system, user = prompt.render(hard_rules_block=hard_rules_prompt_block(rules_dict(cs)), **context)
    model = getattr(cs.ai_models, layer_for(body.step)) or _env_models()[layer_for(body.step)]
    return {"step": body.step, "prompt_version": prompt.version, "based_on_run": run.id, "case_id": run.case_id, "model": model,
            "system": system, "user": user, "chars": len(system) + len(user), "approx_tokens": (len(system) + len(user)) // 4}
