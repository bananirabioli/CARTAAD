"""MockProvider: deterministic, offline outputs built from /fixtures/mock and simple rules. Default provider."""

from collections.abc import Callable
from importlib import import_module
from typing import Any

from app.ai.provider import LLMRequest, ProviderError

# step -> "module:function" inside app.ai.mock
HANDLERS: dict[str, str] = {
    "generate_copy": "compose:compose_copy",
    "check_directive": "directive:check_directive",
    "ocr_vision": "vision:ocr_vision",
    "classify": "classify:classify",
    "interpret": "interpret:interpret",
    "recommend_strategy": "strategy:recommend_strategy",
    "generate_creatives": "creatives:generate_creatives",
    "refine_piece": "refine:refine_piece",
    "red_team": "red_team:red_team",
    "analyze_capture": "mvp:analyze_capture",
    "generate_content": "mvp:generate_content",
    "extract_facts": "mvp:extract_facts",
}


class MockProvider:
    name = "mock"
    model = "mock-deterministic-v1"

    def _handler(self, step: str) -> Callable[[dict[str, Any]], dict[str, Any]]:
        target = HANDLERS.get(step)
        if not target:
            raise ProviderError(f"MockProvider no implementa el paso {step}")
        module, func = target.split(":")
        try:
            return getattr(import_module(f"app.ai.mock.{module}"), func)
        except (ImportError, AttributeError) as exc:
            raise ProviderError(f"MockProvider no implementa el paso {step}") from exc

    def complete(self, request: LLMRequest) -> dict[str, Any]:
        return self._handler(request.step)(request.context)
