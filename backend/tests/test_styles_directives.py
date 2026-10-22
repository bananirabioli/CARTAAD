from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import utcnow
from app.models.ops import RestrictionMode
from app.models.styles import Directive, Style
from app.services.catalog import active_style
from app.services.directive_checker import check_directive
from app.services.style_resolver import LEVEL_STYLE, resolve
from app.validators.style_lint import lint
from tests.conftest import login

CLIENT = 1


def _directive(db, code, **kw):
    base = dict(client_id=CLIENT, code=code, version=1, dtype="vocabulario", title=code, text="", structured={}, scope={}, mandatory="obligatoria", priority=50, status="activa")
    d = Directive(**{**base, **kw})
    db.add(d)
    db.flush()
    return d


# ------------------------------------------------------------------ StyleResolver precedence


def test_resolver_applies_scoped_directives_and_red_lines(db):
    cercano = active_style(db, CLIENT, "cercano")
    r = resolve(db, CLIENT, cercano, topic="baches", flow="A")
    codes = {a.code for a in r.applied}
    assert {"D-001", "D-002"} <= codes
    assert "responsabilidad compartida" in r.mandatory_terms
    assert "por culpa de" in r.prohibited_terms
    assert "mentiroso" in r.prohibited_terms  # from the style itself
    block = r.style_block()
    assert block.startswith("ESTILO: cercano (v1)") and "DIRECTRICES APLICADAS" in block and "[D-002 linea_roja]" in block
    other = resolve(db, CLIENT, cercano, topic="seguridad", flow="A")
    assert "responsabilidad compartida" not in other.mandatory_terms, "D-001 is scoped to baches/agua"


def test_resolver_precedence_mandatory_directive_beats_style_and_style_beats_suggested(db):
    cercano = active_style(db, CLIENT, "cercano")
    _directive(db, "T-1", structured={"vocabulario_obligatorio": ["mentiroso"]}, mandatory="obligatoria")
    r = resolve(db, CLIENT, cercano)
    rule = next(v for v in r.vocab if v.term == "mentiroso" and v.kind == "prohibit")
    assert rule.level == LEVEL_STYLE and not rule.active, "obligatoria (level 4) overrides the style guide (level 5)"
    db.rollback()
    _directive(db, "T-2", structured={"vocabulario_obligatorio": ["mentiroso"]}, mandatory="sugerida")
    r = resolve(db, CLIENT, cercano)
    assert "mentiroso" in r.prohibited_terms, "a suggested directive (level 6) never overrides the style"
    assert "mentiroso" not in r.mandatory_terms


def test_resolver_tie_is_unresolved_and_keeps_prohibition(db):
    cercano = active_style(db, CLIENT, "cercano")
    _directive(db, "T-3", structured={"vocabulario_obligatorio": ["obra emblemática"]}, priority=50)
    _directive(db, "T-4", structured={"vocabulario_prohibido": ["emblemática"]}, priority=50)
    r = resolve(db, CLIENT, cercano)
    assert any(c.get("unresolved") for c in r.conflicts)
    assert "emblemática" in r.prohibited_terms and "obra emblemática" not in r.mandatory_terms


def test_resolver_priority_breaks_ties_within_level(db):
    cercano = active_style(db, CLIENT, "cercano")
    _directive(db, "T-5", structured={"vocabulario_obligatorio": ["obra emblemática"]}, priority=70)
    _directive(db, "T-6", structured={"vocabulario_prohibido": ["emblemática"]}, priority=40)
    r = resolve(db, CLIENT, cercano)
    assert "obra emblemática" in r.mandatory_terms and "emblemática" not in r.prohibited_terms


def test_resolver_veda_legend_and_intensity_clamp(db):
    veda = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == CLIENT))
    veda.starts_at, veda.ends_at = utcnow() - timedelta(days=1), utcnow() + timedelta(days=5)
    _directive(db, "T-7", structured={"vocabulario_prohibido": ["interés público"]}, priority=99, dtype="linea_roja")
    directo = active_style(db, CLIENT, "directo")
    r = resolve(db, CLIENT, directo, adjustments={"intensity": 5})
    assert "Información de interés público." in r.legend_texts
    assert "interés público" not in r.prohibited_terms, "the veda (level 2) beats a red line that would remove its legend"
    assert r.intensity_target == directo.intensity_max == 3, "adjustments never exceed the style maximum"
    assert "[MODO VEDA]" in r.style_block()


# ------------------------------------------------------------------ linter


@pytest.mark.parametrize("bad", ["Eso dice un MENTIROSO.", "Eso dice un mentírosó.", "Eso dice un m e n t i r o s o.", "Eso dice un m3nt1r0s0."])
def test_linter_blocks_prohibited_vocab_even_obfuscated(db, bad):
    r = resolve(db, CLIENT, active_style(db, CLIENT, "cercano"))
    status, findings = lint(bad, r)
    assert status == "block"
    assert any(f.code == "prohibited_term" and f.severity == "block" for f in findings)


def test_linter_legends_length_emoji(db):
    veda = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == CLIENT))
    veda.starts_at = utcnow() - timedelta(days=1)
    r = resolve(db, CLIENT, active_style(db, CLIENT, "directo"))
    status, findings = lint("Dato incorrecto 🙂", r)
    codes = {f.code for f in findings}
    assert status == "block" and {"legend_missing", "emoji", "too_short"} <= codes
    legend_finding = next(f for f in findings if f.code == "legend_missing")
    assert legend_finding.rule_id == "HR-04"
    status, _ = lint("Dato incorrecto sobre baches. El dato: el Municipio Ejemplo reparó baches este semestre. Revise la fuente antes de compartir.\n\nInformación de interés público.", r)
    assert status == "ok"


# ------------------------------------------------------------------ directive checker


def test_hard_rule_directive_is_rejected_and_cannot_activate(client):
    login(client, "analista@demo.mx")
    r = client.post("/directives", json={"dtype": "estilo", "title": "Atajo", "text": "Cuando falte el dato, redondear cifras sin citar fuente."})
    d = r.json()
    assert r.status_code == 201 and d["status"] == "rechazada" and d["conflict_status"] == "rechazada_por_regla_dura"
    assert d["conflict_report"]["hard_rules"][0]["rule_id"] == "HR-01"
    login(client, "admin@demo.mx")
    assert client.post(f"/directives/{d['id']}/transition", json={"status": "activa"}).status_code == 409


def test_conflicting_pair_blocks_until_priority_changes(client):
    login(client, "admin@demo.mx")
    directives = {d["code"]: d for d in client.get("/directives").json()}
    d8 = directives["D-008"]
    assert d8["conflict_status"] == "conflicto_bloqueante"
    r = client.post(f"/directives/{d8['id']}/transition", json={"status": "activa"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "directive_blocked"
    r = client.patch(f"/directives/{d8['id']}", json={"priority": 65})
    assert r.json()["conflict_status"] == "resuelto_por_prioridad"
    r = client.post(f"/directives/{d8['id']}/transition", json={"status": "activa"})
    assert r.status_code == 200 and r.json()["status"] == "activa"


def test_veda_and_style_limit_conflicts(client):
    login(client, "admin@demo.mx")
    directives = {d["code"]: d for d in client.get("/directives").json()}
    assert directives["D-010"]["conflict_status"] == "advertencia"
    assert directives["D-010"]["conflict_report"]["findings"][0]["kind"] == "veda"
    assert directives["D-012"]["conflict_status"] == "conflicto_bloqueante"
    assert directives["D-012"]["conflict_report"]["findings"][0]["kind"] == "estilo"
    assert client.post(f"/directives/{directives['D-010']['id']}/transition", json={"status": "activa"}).status_code == 200, "a warning can be activated"


def test_ai_suggested_conflicts_need_human_confirmation(client):
    login(client, "admin@demo.mx")
    client.post("/directives", json={"dtype": "narrativa", "title": "Mencionar folio", "text": "Siempre mencionar el folio del reporte.", "mandatory": "sugerida"})
    r = client.post("/directives", json={"dtype": "narrativa", "title": "Sin folios", "text": "Evitar el folio del reporte en respuestas públicas.", "mandatory": "sugerida"})
    d = r.json()
    ai = [f for f in d["conflict_report"]["findings"] if f["ai_suggested"]]
    assert ai and d["conflict_status"] == "advertencia"
    r = client.post(f"/directives/{d['id']}/findings", json={"finding_id": ai[0]["id"], "confirmed": False})
    assert r.json()["conflict_status"] == "sin_conflicto"


def test_kb_owner_activates_only_narrative_and_vocabulary(client):
    login(client, "base@demo.mx")
    narr = client.post("/directives", json={"dtype": "narrativa", "title": "Nueva narrativa", "text": "Explicar el plan de renovación de tubería."}).json()
    assert client.post(f"/directives/{narr['id']}/transition", json={"status": "activa"}).status_code == 200
    red = client.post("/directives", json={"dtype": "linea_roja", "title": "Nueva línea roja", "text": "Sin bromas sobre el agua."}).json()
    assert client.post(f"/directives/{red['id']}/transition", json={"status": "activa"}).status_code == 403


def test_directives_isolated_per_client(client):
    login(client, "candidatura@demo.mx")
    titles = {d["title"] for d in client.get("/directives").json()}
    assert "Responsabilidad compartida entre niveles de gobierno" not in titles and "Sin ataques personales" in titles


# ------------------------------------------------------------------ styles lifecycle


def test_editing_active_style_creates_new_version_and_activation_archives_previous(client, db):
    login(client, "admin@demo.mx")
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    cercano = styles["cercano"]
    r = client.patch(f"/styles/{cercano['id']}", json={"prohibited_vocab": ["mentiroso", "corrupto", "flojos"], "change_note": "agrega término"})
    v2 = r.json()
    assert v2["version"] == 2 and v2["status"] == "borrador" and v2["id"] != cercano["id"]
    assert client.post(f"/styles/{v2['id']}/transition", json={"status": "activo"}).status_code == 200
    rows = {s.version: s.status for s in db.scalars(select(Style).where(Style.client_id == CLIENT, Style.slug == "cercano"))}
    assert rows == {1: "archivado", 2: "activo"}


def test_high_risk_style_requires_legal(client):
    login(client, "admin@demo.mx")
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    sat = styles["satirico"]
    draft = client.patch(f"/styles/{sat['id']}", json={"description": "Sátira de roles, revisada."}).json()
    r = client.post(f"/styles/{draft['id']}/transition", json={"status": "activo"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "legal_required"
    login(client, "legal@demo.mx")
    assert client.post(f"/styles/{draft['id']}/legal-approve").status_code == 200
    login(client, "admin@demo.mx")
    assert client.post(f"/styles/{draft['id']}/transition", json={"status": "activo"}).status_code == 200


def test_style_cannot_imitate_third_parties(client):
    login(client, "admin@demo.mx")
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    r = client.patch(f"/styles/{styles['satirico']['id']}", json={"visual_guide": "Títeres inspirados en los Muppets."})
    assert r.status_code == 422 and r.json()["error"]["code"] == "hard_rule" and "HR-10" in r.json()["error"]["message"]


def test_designer_edits_only_visual_guide(client):
    login(client, "diseno@demo.mx")
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    assert client.patch(f"/styles/{styles['cercano']['id']}", json={"visual_guide": "Trazo suave, paleta tierra."}).status_code == 200
    assert client.patch(f"/styles/{styles['cercano']['id']}", json={"intensity_max": 3}).status_code == 403


def test_probar_estilo_produces_clearly_different_styles(client):
    login(client)
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    text = "Llevan meses sin tapar los baches de la avenida y el municipio no hace nada."
    outs = {slug: client.post(f"/styles/{styles[slug]['id']}/test", json={"text": text}).json() for slug in ("institucional", "cercano", "directo")}
    texts = {slug: o["text"] for slug, o in outs.items()}
    assert len(set(texts.values())) == 3
    for o in outs.values():
        assert o["lint_status"] in ("ok", "warn")
        assert any(s["type"] == "asercion_factual" and s["fact_ids"] for s in o["segments"])
        assert any(a["code"] == "D-001" for a in o["resolved"]["applied_directives"])
    assert texts["directo"].startswith("Dato incorrecto") or texts["directo"].startswith("Falta contexto") or "Corrección" in texts["directo"]


def test_export_import_roundtrip(client):
    login(client, "admin@demo.mx")
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    data = client.get(f"/styles/{styles['didactico']['id']}/export").json()
    data["slug"] = "didactico_vecinal"
    data["name"] = "Didáctico vecinal"
    r = client.post("/styles/import", json=data)
    assert r.status_code == 201 and r.json()["status"] == "borrador" and r.json()["guidelines"] == data["guidelines"]


def test_matrix_is_editable_data(client):
    login(client)
    m = client.get("/catalog/matrix").json()
    assert len(m["cells"]) == 16 * 6
    cell = next(c for c in m["cells"] if c["creative_slug"] == "voz_ciudadana" and c["format_slug"] == "formato_voz_pueblo")
    assert cell["level"] == "none" and "HR-07" in cell["note"]
    body = {"creative_slug": "infografia", "format_slug": "formato_titeres", "level": "partial", "note": "Prueba"}
    assert client.put("/catalog/matrix", json=body).status_code == 403
    login(client, "admin@demo.mx")
    assert client.put("/catalog/matrix", json=body).status_code == 200
    m = client.get("/catalog/matrix").json()
    assert next(c for c in m["cells"] if c["creative_slug"] == "infografia" and c["format_slug"] == "formato_titeres")["level"] == "partial"


def test_ai_runs_are_logged_with_style_and_directives(client):
    login(client)
    styles = {s["slug"]: s for s in client.get("/styles").json()}
    client.post(f"/styles/{styles['cercano']['id']}/test", json={})
    runs = client.get("/ai-runs", params={"step": "generate_copy"}).json()["items"]
    assert runs and runs[0]["style_slug"] == "cercano" and runs[0]["prompt_version"] == "3"


def test_checker_marks_directive_with_hard_rule_in_structured_fields(db):
    d = _directive(db, "T-9", status="borrador", structured={"vocabulario_obligatorio": ["usar cuentas anónimas para amplificar"]})
    report = check_directive(db, d, use_ai=False)
    assert report["status"] == "rechazada_por_regla_dura" and report["hard_rules"][0]["rule_id"] == "HR-02"
