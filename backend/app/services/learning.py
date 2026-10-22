"""Learning context (6.8): historical results by topic feed the strategy recommender and the generator.

Always reports sample size; below `learning_min_sample` the app says "muestra insuficiente" instead of recommending.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.i18n import t
from app.models.kb import ResponseHistory


def _rank(rows: list[ResponseHistory], attr: str, min_sample: int) -> list[dict[str, Any]]:
    groups: dict[str, list[ResponseHistory]] = defaultdict(list)
    for r in rows:
        key = getattr(r, attr)
        if key:
            groups[key].append(r)
    out = []
    for key, items in groups.items():
        ok = sum(1 for r in items if r.outcome == "funciono")
        out.append({"value": key, "n": len(items), "ok": ok, "rate": round(ok / len(items), 2), "sufficient": len(items) >= min_sample})
    out.sort(key=lambda g: (g["sufficient"], g["rate"], g["n"]), reverse=True)
    return out


def learning_context(db: Session, client_id: int, topic_slug: str | None, min_sample: int) -> dict[str, Any]:
    rows = list(db.scalars(select(ResponseHistory).where(ResponseHistory.client_id == client_id, ResponseHistory.topic_slug == (topic_slug or ""))))
    return {
        "topic": topic_slug,
        "sample_size": len(rows),
        "min_sample": min_sample,
        "sufficient": len(rows) >= min_sample,
        "styles": _rank(rows, "style_slug", min_sample),
        "formats": _rank(rows, "format_slug", min_sample),
        "strategies": _rank(rows, "strategy", min_sample),
        "creatives": _rank(rows, "creative_slug", min_sample),
    }


def recommend_from(learning: dict[str, Any], key: str, allowed: list[str] | None = None) -> dict[str, Any]:
    """Best option of a dimension (styles / formats / strategies) with its own sample >= min_sample."""
    options = [g for g in learning.get(key, []) if allowed is None or g["value"] in allowed]
    best = next((g for g in options if g["sufficient"] and g["rate"] >= 0.5), None)
    if not best:
        n = sum(g["n"] for g in options)
        return {"value": None, "sufficient": False, "n": n, "reason": t("learning.insufficient", n=n, min=learning.get("min_sample", 5))}
    return {"value": best["value"], "sufficient": True, "n": best["n"], "ok": best["ok"], "rate": best["rate"], "reason": t("learning.worked", ok=best["ok"], n=best["n"])}
