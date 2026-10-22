"""Backend user-facing strings (es-MX). Keys are dotted paths into es_MX.json."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DIR = Path(__file__).parent


@lru_cache
def _catalog() -> dict[str, Any]:
    return json.loads((_DIR / "es_MX.json").read_text(encoding="utf-8"))


def t(key: str, **params: Any) -> str:
    node: Any = _catalog()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]
    if not isinstance(node, str):
        return key
    try:
        return node.format(**params)
    except (KeyError, IndexError):
        return node


def section(key: str) -> dict[str, Any]:
    node: Any = _catalog()
    for part in key.split("."):
        node = node.get(part, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, dict) else {}
