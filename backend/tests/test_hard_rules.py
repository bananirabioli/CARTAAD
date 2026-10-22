"""Each hard rule HR-01…HR-11 has at least one test. They cannot be disabled by configuration."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.guardrails import hard_rules as hr
from app.guardrails.hard_rules import HardRuleViolation, PieceGate


def rules_hit(text: str) -> set[str]:
    return {m.rule_id for m in hr.check_text_against_hard_rules(text)}


def test_registry_complete():
    assert list(hr.HARD_RULES) == [f"HR-{i:02d}" for i in range(1, 12)]
    for rule in hr.HARD_RULES.values():
        assert rule.title and rule.description and rule.patterns
    block = hr.hard_rules_prompt_block()
    assert all(rid in block for rid in hr.HARD_RULES)


# ---------------------------------------------------------------- directive texts that violate rules


@pytest.mark.parametrize(
    ("text", "rule"),
    [
        ("Cuando falte el dato, redondear cifras sin citar fuente.", "HR-01"),
        ("Si no hay dato oficial, estimar la cifra y publicarla.", "HR-01"),
        ("Ocultar la fuente cuando sea de otro nivel de gobierno.", "HR-01"),
        ("Usar cuentas anónimas para amplificar la respuesta.", "HR-02"),
        ("Apoyarse en bots para dar alcance a los carruseles.", "HR-02"),
        ("Guardar los nombres de usuarios que comentan en contra.", "HR-03"),
        ("Ignorar el modo veda en piezas de amplificación.", "HR-04"),
        ("Tratar las quejas ciudadanas como ataque coordinado.", "HR-05"),
        ("Presentar la ilustración generada como foto real de la obra.", "HR-06"),
        ("Quitar la etiqueta ilustración representativa para que se vea más natural.", "HR-07"),
        ("Inventar testimonios de vecinos satisfechos.", "HR-07"),
        ("Atribuir el abandono al Gobierno Estatal sin datos.", "HR-08"),
        ("Publicar directamente sin aprobación cuando sea urgente.", "HR-09"),
        ("Imitar el estilo de los Muppets para los títeres.", "HR-10"),
        ("Generar ilustraciones que incluyan cifras y el logo.", "HR-11"),
    ],
)
def test_violating_directives_are_detected(text, rule):
    assert rule in rules_hit(text)


@pytest.mark.parametrize(
    "text",
    [
        "Usar siempre el término «responsabilidad compartida» al explicar competencias.",
        "Citar siempre la fuente oficial y la fecha del dato.",
        "Nunca ocultar la fuente de un dato.",
        "No usar bots ni cuentas falsas.",
        "Evitar inventar testimonios con nombre o cifra.",
        "Ninguna afirmación sin respaldo en la base.",
        "Evitar publicar sin aprobación humana.",
        "Priorizar temas de agua durante el estiaje.",
        "Leyenda obligatoria: «Información de interés público».",
        "Monitorear publicaciones que parezcan de bots sin responderlas.",
    ],
)
def test_legitimate_directives_pass(text):
    assert rules_hit(text) == set()


# ---------------------------------------------------------------- HR-01


def test_hr01_source_label_never_hides_missing_source():
    fact = SimpleNamespace(fact_date=None)
    label = hr.source_label(fact)
    assert "sin documento de origen" in label and "sin fecha" in label
    label = hr.source_label(SimpleNamespace(fact_date=datetime(2024, 5, 1, tzinfo=UTC)), "Informe 2024")
    assert label == "Fuente: Informe 2024 · 01/05/2024"


def test_hr01_cited_facts_must_be_visible():
    hr.assert_sources_visible(["H-001"], "Fuente: H-001 Informe · 01/05/2024")
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_sources_visible(["H-001", "H-002"], "Fuente: H-001 Informe")
    assert exc.value.rule_id == "HR-01"


# ---------------------------------------------------------------- HR-02


def test_hr02_only_registered_accounts():
    ok = SimpleNamespace(registered=True, verified=True, client_id=1, account_type="aliada")
    hr.assert_registered_account(ok, 1)
    for bad in [
        None,
        SimpleNamespace(registered=False, verified=True, client_id=1, account_type="propia"),
        SimpleNamespace(registered=True, verified=False, client_id=1, account_type="propia"),
        SimpleNamespace(registered=True, verified=True, client_id=2, account_type="propia"),
        SimpleNamespace(registered=True, verified=True, client_id=1, account_type="bot"),
    ]:
        with pytest.raises(HardRuleViolation) as exc:
            hr.assert_registered_account(bad, 1)
        assert exc.value.rule_id == "HR-02"


# ---------------------------------------------------------------- HR-03


def test_hr03_commenter_identity_is_stripped():
    clean, dropped = hr.strip_commenter_identity(
        {"text": "Oye @juan.perez llámame al 33 1234 5678 o escribe a juan@mail.com", "author": "Juan", "handle": "@juan", "likes": 3}
    )
    assert dropped == ["author", "handle"]
    assert "author" not in clean and "handle" not in clean and clean["likes"] == 3
    assert "@juan.perez" not in clean["text"] and "juan@mail.com" not in clean["text"] and "1234" not in clean["text"]


# ---------------------------------------------------------------- HR-04


def test_hr04_veda_blocks_formats_and_creatives_only_while_active():
    now = datetime(2026, 10, 1, tzinfo=UTC)
    veda = SimpleNamespace(
        active=True,
        name="Veda demo",
        starts_at=now - timedelta(days=1),
        ends_at=now + timedelta(days=1),
        blocked_formats=["formato_titeres"],
        blocked_creatives=["agradecimiento"],
        mandatory_legends=["Información de interés público"],
    )
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_not_restricted(veda, now, format_slug="formato_titeres")
    assert exc.value.rule_id == "HR-04"
    with pytest.raises(HardRuleViolation):
        hr.assert_not_restricted(veda, now, creative_slug="agradecimiento")
    hr.assert_not_restricted(veda, now, format_slug="formato_clasico")
    assert hr.required_legends(veda, now) == ["Información de interés público"]
    later = now + timedelta(days=3)
    hr.assert_not_restricted(veda, later, format_slug="formato_titeres")
    assert hr.required_legends(veda, later) == []


# ---------------------------------------------------------------- HR-05


def test_hr05_legit_complaints_are_routed_never_attacked():
    hr.assert_complaint_routing("queja_ciudadana_legitima", True, "contextualizar")
    with pytest.raises(HardRuleViolation):
        hr.assert_complaint_routing("queja_ciudadana_legitima", False)
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_complaint_routing("queja_ciudadana_legitima", True, "desmentir")
    assert exc.value.rule_id == "HR-05"
    hr.assert_complaint_routing("dato_falso", False, "desmentir")


# ---------------------------------------------------------------- HR-06


def test_hr06_generated_images_are_never_evidence():
    hr.assert_evidence_images([{"id": 1, "image_type": "foto_real", "credit": "Archivo municipal"}])
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_evidence_images([{"id": 2, "image_type": "ilustracion", "credit": "Equipo"}])
    assert exc.value.rule_id == "HR-06"
    with pytest.raises(HardRuleViolation):
        hr.assert_evidence_images([{"id": 3, "image_type": "foto_real", "credit": "x", "generada_por_ia": True}])
    with pytest.raises(HardRuleViolation):
        hr.assert_evidence_images([{"id": 4, "image_type": "foto_real", "credit": " "}])
    meta = hr.generated_image_metadata(seed=7)
    assert meta["generada_por_ia"] and meta["ilustracion"] and meta["no_es_evidencia"]


# ---------------------------------------------------------------- HR-07


def test_hr07_consent_and_representative_label():
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_testimony_consent(None)
    assert exc.value.rule_id == "HR-07"
    hr.assert_testimony_consent({"file_path": "c1/consents/x.pdf"})
    hr.assert_representative_label("ILUSTRACIÓN REPRESENTATIVA · vecina de la colonia")
    hr.assert_representative_label("ilustracion representativa")
    with pytest.raises(HardRuleViolation):
        hr.assert_representative_label("Vecina de la colonia")


# ---------------------------------------------------------------- HR-08


def test_hr08_actor_claims_need_valid_facts():
    hr.assert_claims_backed([{"type": "asercion_factual", "text": "x", "fact_ids": [1]}, {"type": "opinion_marcada", "text": "y"}], {1})
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_claims_backed([{"type": "asercion_factual", "text": "El Estado recortó", "fact_ids": []}], {1})
    assert exc.value.rule_id == "HR-08"
    with pytest.raises(HardRuleViolation):
        hr.assert_claims_backed([{"type": "asercion_factual", "text": "x", "fact_ids": [99]}], {1})


# ---------------------------------------------------------------- HR-09


def _gate(**kw) -> PieceGate:
    base = dict(status="pendiente", current_version=2, approved_version=None, figures_total=2, figures_verified=2, blocking_findings=0, legal_required=False, legal_status=None)
    return PieceGate(**{**base, **kw})


def test_hr09_human_approval_and_verified_figures():
    hr.assert_approvable(_gate())
    for bad in [_gate(figures_verified=1), _gate(blocking_findings=1), _gate(legal_required=True, legal_status="pendiente"), _gate(status="descartado")]:
        with pytest.raises(HardRuleViolation) as exc:
            hr.assert_approvable(bad)
        assert exc.value.rule_id == "HR-09"
    hr.assert_publishable(_gate(status="aprobado", approved_version=2))
    with pytest.raises(HardRuleViolation):
        hr.assert_publishable(_gate(status="pendiente"))
    with pytest.raises(HardRuleViolation):  # copilot created v3 after approval of v2
        hr.assert_publishable(_gate(status="aprobado", approved_version=2, current_version=3))


# ---------------------------------------------------------------- HR-10


def test_hr10_no_third_party_imitation_and_legal_for_satire():
    assert hr.check_imitation("Figuras tipo títere de diseño propio que representan instituciones.") == []
    with pytest.raises(HardRuleViolation) as exc:
        hr.assert_no_imitation("Títeres inspirados en los personajes de Plaza Sésamo")
    assert exc.value.rule_id == "HR-10"
    assert hr.requires_legal_review(style_requires_legal=True, satirical=False, names_actor=False)
    assert hr.requires_legal_review(style_requires_legal=False, satirical=True, names_actor=True)
    assert hr.requires_legal_review(False, False, False, message_type="acusacion_o_difamacion")
    assert not hr.requires_legal_review(False, True, False)


# ---------------------------------------------------------------- HR-11


def test_hr11_image_prompts_never_request_text_or_figures():
    prompt, negative = hr.sanitize_image_prompt("flat illustration of a repaired street, warm palette", "blurry")
    assert "text" in negative and "numbers" in negative and "logos" in negative and negative.startswith("blurry")
    for bad in ["poster with the title CONTEXTO", "chart showing 45 percent", "street with the city logo", "portrait of the mayor real face", "in the style of Pixar"]:
        with pytest.raises(HardRuleViolation) as exc:
            hr.sanitize_image_prompt(bad)
        assert exc.value.rule_id == "HR-11"
