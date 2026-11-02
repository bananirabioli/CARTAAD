"""Laboratorio: per-client rules (switches + locked integrity core), model resolution, guides, reanalysis and fact extraction."""

import pytest

from app.ai.prompts import load_prompt
from app.ai.runner import resolve_model
from app.guardrails.hard_rules import (
    HardRuleViolation,
    check_text_against_hard_rules,
    hard_rules_prompt_block,
    rule_enabled,
    sanitize_image_prompt,
    validate_rules_patch,
)
from app.services.client_settings import ClientSettings
from app.services.content import safe_visual_prompt
from tests.conftest import login

TEXT_OFF = {"HR-11T": {"enabled": False}, "HR-11N": {"enabled": False}}


@pytest.fixture
def single(monkeypatch):
    import app.services.capture as capture
    import app.services.cases as cases

    monkeypatch.setattr(capture, "single_analysis", lambda: True)
    monkeypatch.setattr(cases, "single_analysis", lambda: True)


# ------------------------------------------------------------------ rules


def test_locked_rules_cannot_be_switched_off():
    for rule_id in ("HR-01", "HR-02", "HR-03", "HR-06", "HR-07", "HR-08", "HR-10", "HR-11"):
        assert rule_enabled({rule_id: {"enabled": False}}, rule_id)
        with pytest.raises(HardRuleViolation):
            validate_rules_patch({rule_id: {"enabled": False}})


def test_rule_wording_cannot_ask_to_break_a_locked_rule():
    with pytest.raises(HardRuleViolation):
        validate_rules_patch({"HR-01": {"enabled": True, "text": "Si falta el dato, inventa cifras creíbles."}})
    validate_rules_patch({"HR-01": {"enabled": True, "text": "Cada cifra con su fuente y fecha; nunca se inventa una cifra."}})


def test_image_text_switch_keeps_the_prompt():
    prompt = 'Bold poster, headline "AGUA PARA TODOS" at the top, 120 km of new pipes'
    with pytest.raises(HardRuleViolation):
        sanitize_image_prompt(prompt)
    kept, negative = safe_visual_prompt(prompt, "", "fallback", TEXT_OFF)
    assert "AGUA PARA TODOS" in kept and "120" in kept
    assert "text" not in negative.split(", ") and "real person faces" in negative
    # real faces stay forbidden whatever the switches say
    with pytest.raises(HardRuleViolation):
        sanitize_image_prompt("portrait of a real person face of the mayor", "", TEXT_OFF)


def test_prompt_block_follows_switches_and_custom_text():
    rules = {**TEXT_OFF, "HR-04": {"enabled": False}, "HR-02": {"enabled": True, "text": "Solo cuentas reales, nada de bots."}}
    block = hard_rules_prompt_block(rules)
    assert "[HR-04]" not in block and "Solo cuentas reales, nada de bots." in block
    assert "Sí pueden incluir: texto" in block
    assert "[HR-11]" in hard_rules_prompt_block() and "ni texto" in hard_rules_prompt_block()


def test_directive_checker_respects_switches():
    text = "Generar imágenes con titulares grandes"
    assert check_text_against_hard_rules(text)
    assert not check_text_against_hard_rules(text, rules=TEXT_OFF)


def test_lab_api_rules_and_models(client):
    login(client, "admin@demo.mx")
    r = client.put("/lab/rules", json={"rules": {"HR-01": {"enabled": False}}})
    assert r.status_code == 422, r.text
    r = client.put("/lab/rules", json={"rules": {"HR-11T": {"enabled": False}}})
    assert r.status_code == 200, r.text
    hr11 = next(x for x in r.json()["rules"] if x["id"] == "HR-11")
    assert hr11["locked"] and any(s["id"] == "HR-11T" and not s["enabled"] for s in hr11["switches"])
    r = client.put("/lab/models", json={"models": {"text": "openai/gpt-5.5", "image": ""}})
    assert r.status_code == 200 and r.json()["models"]["text"]["effective"] == "openai/gpt-5.5"
    assert r.json()["models"]["image"]["client"] is None
    r = client.put("/lab/guides", json={"guides": {"image": "Fotografía editorial, colores de campaña"}, "facts_top_k": 6})
    assert r.json()["guides"]["image"].startswith("Fotografía") and r.json()["facts_top_k"] == 6
    assert [h["action"] for h in client.get("/lab/history").json()][:3] == ["lab.guides", "lab.models", "lab.rules"]


def test_analyst_cannot_change_lab(client):
    login(client)
    assert client.put("/lab/guides", json={"guides": {"text": "x"}}).status_code == 403


# ------------------------------------------------------------------ models and prompts


def test_model_resolution_order():
    cs = ClientSettings.model_validate({"ai_models": {"analysis": "google/gemini-3-pro", "text": None}})
    assert resolve_model("analyze_capture", cs, "x/run") == "x/run"
    assert resolve_model("analyze_capture", cs) == "google/gemini-3-pro"
    assert resolve_model("generate_content", cs) is None  # .env default


def test_prompts_render_guides_and_context():
    system, user = load_prompt("analyze_capture").render(
        hard_rules_block="", guides={"analysis": "Lee el sarcasmo norteño"}, analyst_context="Es un regidor de oposición", client_name="X", topics=[], facts=[],
    )
    assert "Lee el sarcasmo norteño" in system and "Es un regidor de oposición" in user
    system, user = load_prompt("generate_content").render(
        hard_rules_block="", style_block="", guides={"text": "Humor ligero", "image": "Collage"}, engagement="Gancho con pregunta", text_in_image=True,
        client_name="X", styles=[], facts=[], claims=[], max_images=1, want_video=False,
    )
    assert "Humor ligero" in system and "Collage" in system and "SÍ puede escribir texto" in system and "Gancho con pregunta" in user


# ------------------------------------------------------------------ per-capture context, reanalysis, generation options


def test_capture_context_reanalyze_and_generation_options(client, single):
    login(client)
    r = client.post("/posts/manual", data={"text": "El municipio no ha invertido nada en agua potable este año.", "network": "facebook",
                                           "analyst_context": "Página ligada a un partido opositor", "analysis_model": "google/gemini-3-pro"})
    assert r.status_code == 201, r.text
    case_id = r.json()["case_id"]
    case = client.get(f"/cases/{case_id}").json()
    assert case["lab"]["analyst_context"] == "Página ligada a un partido opositor" and case["lab"]["analysis"]["ai_run_id"]

    r = client.post(f"/cases/{case_id}/reanalyze", json={"context": "Cuenta con 40 mil seguidores", "model": "openai/gpt-5.5"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "interpretado" and r.json()["lab"]["analyst_context"] == "Cuenta con 40 mil seguidores"

    r = client.post(f"/cases/{case_id}/generate-content", json={"strategy": "contextualizar", "image_count": 1, "engagement": "Abrir con una pregunta",
                                                               "models": {"text": "openai/gpt-5.5", "image": "black-forest-labs/flux-3-image"}})
    assert r.status_code == 202, r.text
    opts = r.json()["options"]
    assert opts["engagement"] == "Abrir con una pregunta" and opts["models"]["image"] == "black-forest-labs/flux-3-image"
    copy = next(p for p in r.json()["pieces"] if p["kind"] == "copy")
    assert copy["content"]["meta"]["ai_run_id"]

    r = client.post("/lab/preview", json={"step": "generate_content", "case_id": case_id})
    assert r.status_code == 200, r.text
    assert "Abrir con una pregunta" in r.json()["user"]


# ------------------------------------------------------------------ fact base


def test_extract_facts_from_text_need_approval(client):
    login(client, "base@demo.mx")
    text = ("Informe trimestral de obra pública. Se rehabilitaron 120 km de calles en el suroriente durante el primer semestre. "
            "La red de agua potable llegó a 12 colonias nuevas. El programa atendió a 3,450 personas.")
    r = client.post("/kb/extract-text", json={"title": "Informe de obra 2026 (prueba)", "text": text, "issuer": "Obras Públicas"})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["proposed"] == 3
    pending = client.get("/kb/facts", params={"state": "propuesto", "page_size": 200}).json()["items"]
    ours = [f for f in pending if f["id"] in report["fact_ids"]]
    assert len(ours) == 3 and all(f["source_quote"] and f["document_id"] == report["document_id"] for f in ours)

    from app.db import SessionLocal
    from app.models.kb import Fact
    from app.services.copy_context import relevant_facts

    with SessionLocal() as s:
        cid = s.get(Fact, ours[0]["id"]).client_id
        assert ours[0]["id"] not in [f.id for f in relevant_facts(s, cid, "calles rehabilitadas suroriente", limit=50)]
    r = client.post(f"/kb/facts/{ours[0]['id']}/review", json={"action": "aprobar"})
    assert r.status_code == 200 and r.json()["status"] == "activo"
    with SessionLocal() as s:
        assert ours[0]["id"] in [f.id for f in relevant_facts(s, cid, "calles rehabilitadas suroriente", limit=50)]
    assert client.post(f"/kb/facts/{ours[1]['id']}/review", json={"action": "descartar"}).json()["status"] == "descartado"


def test_quick_source_and_template(client):
    login(client, "base@demo.mx")
    r = client.post("/kb/facts", json={"statement": "Se instalaron 300 luminarias LED en 2026", "value": 300, "unit": "luminarias",
                                       "source_title": "Boletín de alumbrado (prueba)", "source_issuer": "Servicios Públicos"})
    assert r.status_code == 201, r.text
    assert r.json()["document_id"] and r.json()["status"] == "activo"
    assert client.get("/kb/facts-template.csv").text.startswith("code,statement")
