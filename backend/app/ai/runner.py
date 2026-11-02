"""Run one AI step: render the versioned prompt, call the provider, validate with Pydantic (one retry), log AiRun."""

import time
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.ai.prompts import load_prompt
from app.ai.provider import LLMRequest, ProviderError, ProviderRefusal, get_provider
from app.ai.steps import STEP_MODELS

VISION_STEPS = {"analyze_capture", "ocr_vision"}
from app.db import SessionLocal
from app.errors import AppError
from app.guardrails.hard_rules import hard_rules_prompt_block
from app.models.core import Client
from app.models.ops import AiRun
from app.services.client_settings import ClientSettings, get_client_settings, rules_dict
from app.services.audit import _jsonable

MAX_INPUT_CHARS = 60_000


@dataclass
class StepMeta:
    client_id: int | None = None
    user_id: int | None = None
    case_id: int | None = None
    piece_id: int | None = None
    style_id: int | None = None
    style_slug: str | None = None
    style_version: int | None = None
    applied_directives: list[dict[str, Any]] = field(default_factory=list)


def _trim(value: Any) -> Any:
    data = _jsonable(value)
    text = str(data)
    if len(text) <= MAX_INPUT_CHARS:
        return data
    return {"truncated": True, "preview": text[:MAX_INPUT_CHARS]}


def layer_for(step: str) -> str:
    return "analysis" if step in VISION_STEPS else "text"


def resolve_model(step: str, settings: ClientSettings | None, override: str | None = None) -> str | None:
    """Run override > client default (Laboratorio → Modelos) > .env. None lets the provider decide."""
    if override and override.strip():
        return override.strip()
    if settings is not None:
        chosen = getattr(settings.ai_models, layer_for(step), None)
        if chosen:
            return chosen
    return None


def run_step(
    db: Session, step: str, context: dict[str, Any], meta: StepMeta | None = None, image: tuple[bytes, str] | None = None, model: str | None = None
) -> tuple[BaseModel, AiRun]:
    meta = meta or StepMeta()
    model_cls = STEP_MODELS[step]
    prompt = load_prompt(step)
    client = db.get(Client, meta.client_id) if meta.client_id else None
    settings = get_client_settings(client) if client else None
    rules = rules_dict(settings) if settings else None
    guides = settings.ai_guides.model_dump() if settings else {}
    render_ctx = {"guides": guides, **context}
    system, body = prompt.render(hard_rules_block=hard_rules_prompt_block(rules), **render_ctx)
    provider = get_provider()
    chosen = resolve_model(step, settings, model) if provider.name == "openrouter" else None
    run = AiRun(
        client_id=meta.client_id, step=step, prompt_version=prompt.version, provider=provider.name,
        model=chosen or (provider.model_for(step) if hasattr(provider, "model_for") else provider.model),
        input=_trim({"context": context, "prompt_chars": len(system) + len(body)}), user_id=meta.user_id, case_id=meta.case_id,
        piece_id=meta.piece_id, style_id=meta.style_id, style_slug=meta.style_slug, style_version=meta.style_version,
        applied_directives=_jsonable(meta.applied_directives),
    )
    request = LLMRequest(step=step, system=system, prompt=body, context=context, output_model=model_cls, image=image, model=chosen)
    started = time.perf_counter()
    result: BaseModel | None = None
    try:
        for attempt in (1, 2):
            run.attempts = attempt
            raw = provider.complete(request)
            try:
                result = model_cls.model_validate(raw)
                break
            except ValidationError as exc:
                if attempt == 2:
                    raise ProviderError(f"salida inválida tras reintento: {exc.errors()[:3]}") from exc
                request.feedback = str(exc.errors()[:5])
                run.status = "retried"
    except ProviderRefusal as exc:
        run.status, run.error = "refused", str(exc)
    except ProviderError as exc:
        run.status, run.error = "error", str(exc)
    run.latency_ms = int((time.perf_counter() - started) * 1000)
    if result is None:
        # Failed runs are logged in their own transaction so the caller's rollback does not erase them.
        with SessionLocal() as log_db:
            log_db.add(run)
            log_db.commit()
            run_id = run.id
        raise AppError(502, "ai_error", f"La IA no pudo completar «{step}»: {run.error}", details={"ai_run_id": run_id})
    run.output = _jsonable(result.model_dump())
    db.add(run)
    db.flush()
    return result, run
