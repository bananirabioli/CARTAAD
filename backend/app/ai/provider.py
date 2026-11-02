"""LLMProvider interface and selection. MockProvider is the default (offline, deterministic)."""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

from pydantic import BaseModel

from app.config import get_settings


class ProviderError(Exception):
    pass


class ProviderRefusal(ProviderError):
    def __init__(self, category: str | None, explanation: str | None):
        super().__init__(f"refusal: {category or ''} {explanation or ''}".strip())
        self.category = category
        self.explanation = explanation


@dataclass
class LLMRequest:
    step: str
    system: str
    prompt: str
    context: dict[str, Any]
    output_model: type[BaseModel]
    image: tuple[bytes, str] | None = None
    feedback: str | None = None  # validation error from the previous attempt
    model: str | None = None  # resolved model id (run override > client default > .env)
    meta: dict[str, Any] = field(default_factory=dict)


class LLMProvider(Protocol):
    name: str
    model: str

    def complete(self, request: LLMRequest) -> dict[str, Any]: ...


@lru_cache
def get_provider(name: str | None = None) -> LLMProvider:
    choice = (name or get_settings().llm_provider).lower()
    if choice == "openrouter":
        from app.ai.openrouter import OpenRouterProvider

        return OpenRouterProvider()
    if choice == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    from app.ai.mock_provider import MockProvider

    return MockProvider()
