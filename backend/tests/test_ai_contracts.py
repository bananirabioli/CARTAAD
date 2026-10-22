"""Prompts and JSON schemas are versioned files; they must stay in sync with the code."""

from app.ai.prompts import load_prompt
from app.ai.steps import STEP_MODELS
from app.config import SCHEMAS_DIR
from app.scripts.export_schemas import render


def test_schema_files_match_pydantic_models():
    for step, text in render().items():
        path = SCHEMAS_DIR / f"{step}.json"
        assert path.exists(), f"falta {path.name}: corre `python -m app.scripts.export_schemas`"
        assert path.read_text(encoding="utf-8") == text, f"{path.name} desactualizado: corre `python -m app.scripts.export_schemas`"


def test_every_step_has_a_versioned_prompt_with_grounding_rules():
    for step in STEP_MODELS:
        prompt = load_prompt(step)
        assert prompt.version != "0" and prompt.system and prompt.body
    for step in ("interpret", "generate_copy", "generate_creatives", "refine_piece"):
        system = load_prompt(step).system
        assert "fact_id" in system and "Nunca inventes cifras" in system
    for step in ("generate_copy", "generate_creatives", "refine_piece"):
        assert "{{ style_block }}" in load_prompt(step).system
