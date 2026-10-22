"""AnthropicProvider: structured outputs via messages.parse(output_format=<Pydantic model>).

The model id comes from LLM_MODEL (never hard-coded). Vision steps send the capture as a base64 image block.
"""

import base64
from typing import Any

import anthropic

from app.ai.provider import LLMRequest, ProviderError, ProviderRefusal
from app.config import get_settings


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        s = get_settings()
        if not s.llm_model:
            raise ProviderError("LLM_MODEL es obligatorio cuando LLM_PROVIDER=anthropic")
        self.model = s.llm_model
        self.max_tokens = s.llm_max_tokens
        self.client = anthropic.Anthropic(api_key=s.anthropic_api_key) if s.anthropic_api_key else anthropic.Anthropic()

    def complete(self, request: LLMRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        if request.image:
            data, media_type = request.image
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": base64.standard_b64encode(data).decode()}})
        text = request.prompt
        if request.feedback:
            text += f"\n\nTu respuesta anterior no cumplió el esquema: {request.feedback}\nCorrígela y responde solo con el JSON válido."
        content.append({"type": "text", "text": text})
        try:
            response = self.client.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                system=request.system,
                messages=[{"role": "user", "content": content}],
                output_format=request.output_model,
            )
        except anthropic.BadRequestError as exc:
            raise ProviderError(f"solicitud inválida: {exc.message}") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("límite de uso de la API alcanzado; reintenta más tarde") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"error de la API ({exc.status_code}): {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("no se pudo conectar con la API de Anthropic") from exc
        if response.stop_reason == "refusal":
            details = response.stop_details
            raise ProviderRefusal(getattr(details, "category", None), getattr(details, "explanation", None))
        if response.stop_reason == "max_tokens":
            raise ProviderError("la respuesta se cortó por max_tokens (aumenta LLM_MAX_TOKENS)")
        parsed = response.parsed_output
        if parsed is None:
            raise ProviderError("la respuesta no trajo una salida estructurada")
        return parsed.model_dump()
