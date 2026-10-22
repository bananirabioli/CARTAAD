"""Write /schemas/<step>.json from the Pydantic step models (source of truth: app/ai/steps.py)."""

import json

from app.ai.steps import STEP_MODELS
from app.config import SCHEMAS_DIR


def render() -> dict[str, str]:
    return {step: json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n" for step, model in STEP_MODELS.items()}


if __name__ == "__main__":
    SCHEMAS_DIR.mkdir(exist_ok=True)
    for step, text in render().items():
        (SCHEMAS_DIR / f"{step}.json").write_text(text, encoding="utf-8")
    print(f"{len(STEP_MODELS)} esquemas → {SCHEMAS_DIR}")
