"""Loads MockProvider fixtures from /fixtures/mock. Custom styles reuse the closest base fixture by tags."""

import json
from functools import lru_cache
from typing import Any

from app.config import FIXTURES_DIR

STYLE_DIR = FIXTURES_DIR / "mock" / "styles"


@lru_cache
def style_fixtures() -> dict[str, dict[str, Any]]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(STYLE_DIR.glob("*.json"))}


@lru_cache
def base_style_tags() -> dict[str, dict[str, list[str]]]:
    from app.seed.catalog_data import STYLES

    return {s["slug"]: s["tags"] for s in STYLES}


def fixture_for_style(slug: str, tags: dict[str, list[str]] | None = None) -> tuple[str, dict[str, Any]]:
    """Return (fixture_slug, fixture). Exact slug first; otherwise the base style with most tag overlap."""
    fixtures = style_fixtures()
    if slug in fixtures:
        return slug, fixtures[slug]
    tags = tags or {}
    best, best_score = "institucional", -1.0
    weights = {"tono": 3.0, "intencion": 2.0, "registro": 1.5, "humor": 1.0, "audiencia": 0.5}
    for base_slug, base_tags in base_style_tags().items():
        score = sum(w * len(set(tags.get(dim, [])) & set(base_tags.get(dim, []))) for dim, w in weights.items())
        if score > best_score and base_slug in fixtures:
            best, best_score = base_slug, score
    return best, fixtures[best]


@lru_cache
def mock_json(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / "mock" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
