"""OpenRouter: one API key for text/vision (chat completions with JSON schema), images and video.

Model ids come from settings (OPENROUTER_MODEL_*), never from code paths. Errors become ProviderError with Spanish
messages so the UI can show them as-is.
"""

import base64
import json
import time
from typing import Any

import httpx

from app.ai.provider import LLMRequest, ProviderError, ProviderRefusal
from app.config import get_settings

VISION_STEPS = {"analyze_capture", "ocr_vision"}
TIMEOUT = httpx.Timeout(180, connect=15)


def _headers() -> dict[str, str]:
    s = get_settings()
    if not s.openrouter_api_key:
        raise ProviderError("Falta OPENROUTER_API_KEY: agrégala al archivo .env y reinicia api y worker.")
    return {"Authorization": f"Bearer {s.openrouter_api_key}", "HTTP-Referer": s.openrouter_app_url, "X-Title": "CARTAAD", "Content-Type": "application/json"}


def _raise_for(resp: httpx.Response) -> None:
    if resp.status_code < 400:
        return
    try:
        detail = resp.json().get("error", {}).get("message") or resp.text
    except ValueError:
        detail = resp.text
    detail = str(detail)[:300]
    if resp.status_code == 401:
        raise ProviderError("OpenRouter rechazó la API key (401). Revisa OPENROUTER_API_KEY.")
    if resp.status_code == 402:
        raise ProviderError("OpenRouter: créditos insuficientes (402). Recarga saldo en openrouter.ai.")
    if resp.status_code == 429:
        raise ProviderError("OpenRouter: límite de uso alcanzado (429); reintenta en un momento.")
    raise ProviderError(f"OpenRouter respondió {resp.status_code}: {detail}")


def request(method: str, path: str, **kwargs: Any) -> httpx.Response:
    s = get_settings()
    url = path if path.startswith("http") else f"{s.openrouter_base_url}{path}"
    try:
        resp = httpx.request(method, url, headers=_headers(), timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    except httpx.HTTPError as exc:
        raise ProviderError(f"No se pudo conectar con OpenRouter: {exc.__class__.__name__}") from exc
    _raise_for(resp)
    return resp


_UNSUPPORTED = ("default", "title", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems", "minLength", "maxLength")


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """OpenAI-style strict mode: every object lists all its properties as required and forbids extras.
    Numeric/length constraints are dropped (not every provider accepts them); Pydantic still validates them."""
    if isinstance(schema, dict):
        for key in _UNSUPPORTED:
            if not isinstance(schema.get(key), dict):  # keep a property literally named "title"/"default"
                schema.pop(key, None)
        if schema.get("type") == "object" and "properties" in schema:
            schema["required"] = list(schema["properties"])
            schema["additionalProperties"] = False
        for value in schema.values():
            if isinstance(value, dict):
                _strict_schema(value)
            elif isinstance(value, list):
                for item in value:
                    _strict_schema(item)
    return schema


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ProviderError("la respuesta no trajo JSON")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ProviderError(f"JSON inválido en la respuesta: {exc.msg}") from exc


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self) -> None:
        s = get_settings()
        self.model = s.openrouter_model_text
        self.max_tokens = s.llm_max_tokens

    def model_for(self, step: str) -> str:
        s = get_settings()
        return s.openrouter_model_analysis if step in VISION_STEPS else s.openrouter_model_text

    def complete(self, request_: LLMRequest) -> dict[str, Any]:
        content: list[dict[str, Any]] = []
        text = request_.prompt
        if request_.feedback:
            text += f"\n\nTu respuesta anterior no cumplió el esquema: {request_.feedback}\nCorrígela y responde solo con el JSON válido."
        content.append({"type": "text", "text": text})
        if request_.image:
            data, mime = request_.image
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.standard_b64encode(data).decode()}"}})
        schema = _strict_schema(request_.output_model.model_json_schema())
        body = {
            "model": request_.model or self.model_for(request_.step),
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": request_.system + "\n\nResponde únicamente con un objeto JSON válido que cumpla el esquema."},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_schema", "json_schema": {"name": request_.step, "strict": True, "schema": schema}},
        }
        try:
            data = request("POST", "/chat/completions", json=body).json()
        except ProviderError as exc:
            if "respondió 4" not in str(exc):
                raise
            # Not every model supports strict json_schema: ask for plain JSON (the schema goes in the prompt) and parse it.
            body.pop("response_format")
            body["messages"][0]["content"] += "\n\nEsquema JSON de la respuesta:\n" + json.dumps(schema, ensure_ascii=False)
            data = request("POST", "/chat/completions", json=body).json()
        if data.get("error"):
            raise ProviderError(f"OpenRouter: {data['error'].get('message', data['error'])}")
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise ProviderRefusal("refusal", str(message["refusal"])[:300])
        if choice.get("finish_reason") == "length":
            raise ProviderError("la respuesta se cortó por longitud (aumenta LLM_MAX_TOKENS)")
        return _parse_json(message.get("content") or "")


# ------------------------------------------------------------------ images


def generate_image(prompt: str, aspect_ratio: str = "1:1", model: str | None = None) -> tuple[bytes, str]:
    s = get_settings()
    body = {
        "model": model or s.openrouter_model_image,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
        "image_config": {"aspect_ratio": aspect_ratio},
    }
    try:
        data = request("POST", "/chat/completions", json=body).json()
    except ProviderError as exc:
        if "respondió 4" not in str(exc):
            raise
        body["modalities"] = ["image"]  # image-only models (FLUX, Seedream…) reject the text modality
        data = request("POST", "/chat/completions", json=body).json()
    message = ((data.get("choices") or [{}])[0]).get("message") or {}
    for img in message.get("images") or []:
        url = (img.get("image_url") or {}).get("url", "")
        if url.startswith("data:"):
            header, b64 = url.split(",", 1)
            return base64.b64decode(b64), header[5:].split(";")[0] or "image/png"
        if url.startswith("http"):
            resp = httpx.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.content, resp.headers.get("content-type", "image/png")
    raise ProviderError("el modelo de imagen no devolvió ninguna imagen")


# ------------------------------------------------------------------ video


def _snap_duration(model: str, wanted: int) -> int:
    try:
        resp = httpx.get(f"{get_settings().openrouter_base_url}/videos/models", timeout=30)
        models = {m["id"]: m for m in resp.json().get("data", [])}
        durations = sorted(models.get(model, {}).get("supported_durations") or [])
    except (httpx.HTTPError, ValueError, KeyError):
        durations = []
    if not durations:
        return wanted
    fitting = [d for d in durations if d <= wanted]
    return fitting[-1] if fitting else durations[0]


def generate_video(prompt: str, *, aspect_ratio: str = "9:16", duration: int | None = None, model: str | None = None) -> tuple[bytes, dict[str, Any]]:
    """Submit a video job, poll until it finishes and download the first MP4. Blocking: call it from the worker."""
    s = get_settings()
    model = model or s.openrouter_model_video
    seconds = _snap_duration(model, duration or s.video_max_seconds)
    job = request("POST", "/videos", json={
        "model": model, "prompt": prompt, "duration": seconds, "resolution": s.openrouter_video_resolution,
        "aspect_ratio": aspect_ratio, "generate_audio": False,
    }).json()
    job_id = job.get("id")
    if not job_id:
        raise ProviderError(f"OpenRouter no devolvió id de video: {str(job)[:200]}")
    deadline = time.monotonic() + s.video_timeout_seconds
    status = job
    while status.get("status") != "completed":
        if status.get("status") in ("failed", "cancelled", "expired"):
            raise ProviderError(f"el video terminó como {status.get('status')}: {status.get('error') or ''}".strip())
        if time.monotonic() > deadline:
            raise ProviderError("el video tardó demasiado; revisa el job en OpenRouter")
        time.sleep(s.video_poll_seconds)
        status = request("GET", status.get("polling_url") or f"/videos/{job_id}").json()
    urls = status.get("unsigned_urls") or []
    url = urls[0] if urls else f"/videos/{job_id}/content?index=0"
    if url.startswith("https://openrouter.ai/api/") or not url.startswith("http"):
        resp = request("GET", url, timeout=httpx.Timeout(300, connect=15))
    else:
        resp = httpx.get(url, timeout=httpx.Timeout(300, connect=15))
        resp.raise_for_status()
    return resp.content, {"provider": "openrouter", "model": model, "job_id": job_id, "duration": seconds, "aspect_ratio": aspect_ratio}
