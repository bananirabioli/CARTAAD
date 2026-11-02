"""ImageProvider contract. Image models only produce illustrations: never text, figures, logos, real faces or
third-party works (HR-11). Titles, figures and sources are overlaid by the HTML templates.

* PlaceholderImageProvider (default): code-drawn flat illustrations in the style palette.
* ExternalImageProvider: documented adapter for a real generator; disabled unless EXTERNAL_IMAGE_ENABLED=true.
"""

import hashlib
import io
import random
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

import httpx
from PIL import Image, ImageDraw

from app.config import get_settings
from app.guardrails.hard_rules import generated_image_metadata, sanitize_image_prompt

ASPECTS = {"1:1": (1080, 1080), "4:5": (1080, 1350), "16:9": (1280, 720)}


@dataclass
class ImageSpec:
    prompt: str
    aspect_ratio: str = "1:1"
    seed: int = 7
    negative_prompt: str = ""
    referencias: list[int] = field(default_factory=list)  # ApprovedImage ids (style/composition reference only)
    kind: str = "scene"  # scene | figures | puppets | panels
    palette: list[str] = field(default_factory=list)


@dataclass
class ImageResult:
    data: bytes
    mime: str
    meta: dict[str, Any]


class ImageProvider(Protocol):
    name: str

    def generate(self, spec: ImageSpec) -> ImageResult: ...


def _hex(c: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    m = re.fullmatch(r"#?([0-9a-fA-F]{6})", c.strip())
    return tuple(int(m.group(1)[i : i + 2], 16) for i in (0, 2, 4)) if m else fallback  # type: ignore[return-value]


class PlaceholderImageProvider:
    name = "placeholder"
    version = "1"

    def generate(self, spec: ImageSpec) -> ImageResult:
        w, h = ASPECTS.get(spec.aspect_ratio, ASPECTS["1:1"])
        rnd = random.Random(spec.seed)
        palette = [_hex(c, (120, 120, 140)) for c in spec.palette] or [(52, 76, 120), (226, 150, 80), (120, 170, 150), (210, 90, 90)]
        bg = tuple(min(255, int(v * 0.15 + 225)) for v in palette[0])
        img = Image.new("RGB", (w, h), bg)
        d = ImageDraw.Draw(img)
        if spec.kind in ("figures", "puppets"):
            n = 3 if spec.kind == "puppets" else 4
            d.rectangle([0, int(h * 0.78), w, h], fill=tuple(int(v * 0.8) for v in palette[-1]))
            if spec.kind == "puppets":  # simple stage curtains
                d.rectangle([0, 0, int(w * 0.08), h], fill=palette[0])
                d.rectangle([int(w * 0.92), 0, w, h], fill=palette[0])
            for i in range(n):
                cx = int(w * (i + 1) / (n + 1))
                color = palette[(i + 1) % len(palette)]
                body_w = int(w * 0.16)
                top = int(h * (0.42 if spec.kind == "figures" else 0.38)) + rnd.randint(-20, 20)
                d.rounded_rectangle([cx - body_w // 2, top + 110, cx + body_w // 2, int(h * 0.8)], radius=60, fill=color)
                d.ellipse([cx - 70, top - 30, cx + 70, top + 110], fill=(236, 214, 186) if spec.kind == "figures" else tuple(min(255, v + 60) for v in color))
                if spec.kind == "puppets":  # button eyes, no faces of real people
                    d.ellipse([cx - 35, top + 25, cx - 15, top + 45], fill=(30, 30, 30))
                    d.ellipse([cx + 15, top + 25, cx + 35, top + 45], fill=(30, 30, 30))
                    d.rectangle([cx - body_w // 2 - 10, top + 150, cx + body_w // 2 + 10, top + 210], fill=(250, 250, 250))  # blank sign (label added by template)
        elif spec.kind == "panels":
            cols, rows = 2, 2
            for r in range(rows):
                for c in range(cols):
                    x0, y0 = int(w * c / cols) + 18, int(h * r / rows) + 18
                    x1, y1 = int(w * (c + 1) / cols) - 18, int(h * (r + 1) / rows) - 18
                    d.rectangle([x0, y0, x1, y1], outline=(40, 40, 40), width=6, fill=(250, 250, 250))
                    color = palette[(r * cols + c) % len(palette)]
                    d.ellipse([x0 + 40, y1 - 220, x0 + 140, y1 - 120], fill=color)
                    d.rounded_rectangle([x0 + 30, y1 - 120, x0 + 150, y1 - 20], radius=30, fill=color)
                    d.polygon([(x1 - 60, y0 + 60), (x1 - 160, y0 + 160), (x1 - 40, y0 + 140)], fill=palette[(r + c + 1) % len(palette)])
        else:
            for _ in range(14):
                color = palette[rnd.randrange(len(palette))]
                x, y, s = rnd.randint(0, w), rnd.randint(0, h), rnd.randint(60, 260)
                if rnd.random() < 0.5:
                    d.ellipse([x - s, y - s, x + s, y + s], fill=color)
                else:
                    d.rounded_rectangle([x - s, y - s // 2, x + s, y + s // 2], radius=30, fill=color)
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        meta = generated_image_metadata(prompt_hash=hashlib.sha256(spec.prompt.encode()).hexdigest()[:16], seed=spec.seed, provider=self.name, version=self.version, kind=spec.kind)
        return ImageResult(buf.getvalue(), "image/png", meta)


class ExternalImageProvider:
    """Adapter for an external generator (disabled by default).

    POST {EXTERNAL_IMAGE_URL} with JSON {prompt, negative_prompt, aspect_ratio, seed} and header Authorization: Bearer
    {EXTERNAL_IMAGE_API_KEY}; expects image bytes back. The prompt is sanitized first (HR-11) and the result always carries
    generada_por_ia / ilustracion / no_es_evidencia metadata (HR-06).
    """

    name = "external"
    version = "1"

    def generate(self, spec: ImageSpec) -> ImageResult:
        s = get_settings()
        if not (s.external_image_enabled and s.external_image_url):
            raise RuntimeError("ExternalImageProvider está desactivado (EXTERNAL_IMAGE_ENABLED / EXTERNAL_IMAGE_URL).")
        resp = httpx.post(
            s.external_image_url,
            json={"prompt": spec.prompt, "negative_prompt": spec.negative_prompt, "aspect_ratio": spec.aspect_ratio, "seed": spec.seed},
            headers={"Authorization": f"Bearer {s.external_image_api_key or ''}"},
            timeout=120,
        )
        resp.raise_for_status()
        meta = generated_image_metadata(prompt_hash=hashlib.sha256(spec.prompt.encode()).hexdigest()[:16], seed=spec.seed, provider=self.name, version=self.version)
        return ImageResult(resp.content, resp.headers.get("content-type", "image/png"), meta)


class OpenRouterImageProvider:
    """Image models through OpenRouter (chat completions with modalities image+text). Prompts arrive sanitized (HR-11)."""

    name = "openrouter"
    version = "1"

    def generate(self, spec: ImageSpec) -> ImageResult:
        from app.ai.openrouter import generate_image

        prompt = spec.prompt
        if spec.negative_prompt:
            prompt += f"\nAvoid: {spec.negative_prompt}"
        data, mime = generate_image(prompt, spec.aspect_ratio)
        meta = generated_image_metadata(prompt_hash=hashlib.sha256(spec.prompt.encode()).hexdigest()[:16], seed=spec.seed, provider=self.name, version=self.version, kind=spec.kind)
        meta["model"] = get_settings().openrouter_model_image
        return ImageResult(data, mime, meta)


@lru_cache
def get_image_provider() -> ImageProvider:
    s = get_settings()
    if s.image_provider == "openrouter":
        return OpenRouterImageProvider()
    return ExternalImageProvider() if s.image_provider == "external" and s.external_image_enabled else PlaceholderImageProvider()


_STRIP = re.compile(r"#[0-9a-fA-F]{3,6}|\d+|[«»\"']")


def build_image_spec(visual_guide: str, description: str, *, kind: str, palette: list[str], seed: int, aspect_ratio: str = "1:1") -> ImageSpec:
    """Compose an illustration prompt from the style's visual guide and the piece description, then sanitize (HR-11)."""
    base = _STRIP.sub("", f"Flat original illustration, own design. {description}. Visual guide: {visual_guide}")
    base = re.sub(r"\s+", " ", base).strip()
    try:
        prompt, negative = sanitize_image_prompt(base)
    except Exception:  # noqa: BLE001 - fall back to a neutral, always-valid prompt
        prompt, negative = sanitize_image_prompt(f"Flat original illustration, own design, soft shapes, {kind}")
    return ImageSpec(prompt=prompt, negative_prompt=negative, aspect_ratio=aspect_ratio, seed=seed, kind=kind, palette=palette)
