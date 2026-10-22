"""Versioned prompts in /prompts/<step>.md: YAML-ish front matter + Jinja2 body."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from jinja2 import Environment

from app.config import PROMPTS_DIR

_env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)


@dataclass(frozen=True)
class Prompt:
    step: str
    version: str
    system: str
    body: str

    def render(self, **context: Any) -> tuple[str, str]:
        return _env.from_string(self.system).render(**context).strip(), _env.from_string(self.body).render(**context).strip()


def _parse(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        for line in front.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        return meta, body
    return meta, text


@lru_cache
def load_prompt(step: str) -> Prompt:
    meta, body = _parse((PROMPTS_DIR / f"{step}.md").read_text(encoding="utf-8"))
    system, _, user = body.partition("## Usuario")
    system = system.replace("## Sistema", "", 1)
    return Prompt(step=step, version=meta.get("version", "0"), system=system.strip(), body=user.strip())
