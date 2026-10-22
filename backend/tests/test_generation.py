from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models.ops import RestrictionMode
from tests.conftest import login


def _cases(client, **filters):
    return client.get("/cases", params={"page_size": 200, **filters}).json()["items"]


def _account(client, fmt):
    return next(a for a in client.get("/accounts").json() if a["format_slug"] == fmt and a["registered"] and a["account_type"] == "propia")


def _ready_case(client, fmt="formato_clasico", message_type="dato_sacado_de_contexto", topic="baches", style=None):
    case = next(c for c in _cases(client, status="interpretado", topic=topic) if c["message_type"] == message_type)
    body = {"decision": "responder", "account_id": _account(client, fmt)["id"]}
    if style:
        body["style_slug"] = style
    d = client.post(f"/cases/{case['id']}/decide", json=body).json()
    assert d["status"] == "listo_para_generar", d
    return d


def _generate(client, case_id):
    r = client.post(f"/cases/{case_id}/generate", json={})
    assert r.status_code == 202, r.text
    proposal = r.json()
    assert proposal["status"] == "listo", proposal
    return proposal


def test_generation_produces_style_variants_and_creatives(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    copies = [p for p in proposal["pieces"] if p["kind"] == "copy"]
    creatives = [p for p in proposal["pieces"] if p["kind"] == "creative"]
    assert len(copies) == 3 and {p["style_slug"] for p in copies} == {"institucional", "cercano", "directo"}
    texts = [" ".join(s["text"] for s in p["content"]["segments"]) for p in copies]
    assert len(set(texts)) == 3, "the same case yields clearly different variants per style"
    assert 5 <= len(creatives) <= 10
    for p in proposal["pieces"]:
        assert p["style_version"] >= 1 and p["applied_directives"] and p["why"]
        assert f"estilo:{p['style_slug']}" in p["effective_tags"] and "flujo:A" in p["effective_tags"]
    partial = [p for p in creatives if p["creative_slug"] in ("infografia",)]
    assert all(p["adaptation"] for p in partial), "◐ creatives explain the adaptation"
    assert all(p["render_status"] in ("listo", "no_aplica") for p in creatives)
    assert all(p["risk_score"] is not None for p in proposal["pieces"])
    detail = client.get(f"/cases/{case['id']}").json()
    assert detail["status"] == "generado"


def test_matrix_none_creatives_are_never_generated(client):
    login(client)
    case = _ready_case(client, fmt="formato_titeres")
    proposal = _generate(client, case["id"])
    excluded = {e["slug"] for e in proposal["excluded_creatives"]}
    generated = {p["creative_slug"] for p in proposal["pieces"] if p["kind"] == "creative"}
    assert {"infografia", "dato_duro", "voz_ciudadana"} <= excluded
    assert not generated & excluded


def test_satirical_style_requires_legal_before_approval(client):
    login(client)
    case = _ready_case(client, fmt="formato_titeres")
    proposal = _generate(client, case["id"])
    sat = [p for p in proposal["pieces"] if p["style_slug"] == "satirico"]
    assert sat and all(p["legal_required"] and p["legal_status"] == "pendiente" for p in sat)
    piece = client.get(f"/pieces/{sat[0]['id']}").json()
    assert any("legal" in b.lower() for b in piece["approval_blockers"])
    illustrated = [p for p in sat if p["kind"] == "creative" and any(i.get("generated") for i in p["content"].get("images", []))]
    assert illustrated and all(i["meta"]["generada_por_ia"] and i["meta"]["no_es_evidencia"] for p in illustrated for i in p["content"]["images"] if i.get("generated"))
    login(client, "legal@demo.mx")
    r = client.post(f"/pieces/{sat[0]['id']}/legal", json={"action": "liberar", "note": "Sátira sobre roles; sin personas identificables."})
    assert r.json()["legal_status"] == "liberada"


def test_copilot_respects_style_limits_and_revalidates(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    inst = next(p for p in proposal["pieces"] if p["kind"] == "copy" and p["style_slug"] == "institucional")
    pid = inst["id"]
    piece = client.get(f"/pieces/{pid}").json()
    for fig in piece["figures"]:
        client.post(f"/pieces/{pid}/figures/{fig['id']}/verify", json={"status": "verificada"})
    piece = client.get(f"/pieces/{pid}").json()
    assert piece["figures_verified"] == piece["figures_total"] > 0
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "mas_firme"}).json()
    assert r["applied"] and r["piece"]["current_version"] == 2 and r["piece"]["intensity"] == 2
    assert r["piece"]["figures_verified"] == 0, "a new version invalidates human verifications"
    assert r["piece"]["versions"][0]["diff"] and r["piece"]["versions"][0]["author_type"] == "ia"
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "mas_firme"}).json()
    assert not r["applied"] and r["suggested_style"] == "directo" and "intensidad máxima" in r["message"]
    assert r["piece"]["current_version"] == 2


def test_copilot_actions_add_fact_change_style_revert_and_hard_rules(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    piece = next(p for p in proposal["pieces"] if p["kind"] == "copy" and p["style_slug"] == "cercano")
    pid = piece["id"]
    before_facts = sum(1 for s in piece["content"]["segments"] if s["type"] == "asercion_factual")
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "agregar_dato"}).json()
    assert r["applied"] and sum(1 for s in r["piece"]["content"]["segments"] if s["type"] == "asercion_factual") == before_facts + 1
    assert client.post(f"/pieces/{pid}/copilot", json={"action": "cambiar_estilo", "style_slug": "satirico"}).status_code == 422
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "cambiar_estilo", "style_slug": "empatico"}).json()
    assert r["applied"] and r["piece"]["style_slug"] == "empatico"
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "libre", "instruction": "Inventa una cifra de baches para que suene más fuerte."}).json()
    assert not r["applied"] and r["rule_id"] == "HR-01"
    r = client.post(f"/pieces/{pid}/copilot", json={"action": "mas_formal"}).json()
    assert not r["applied"] and "institucional" in r["message"], "empático is cotidiano: a formal register needs another style"
    r = client.post(f"/pieces/{pid}/revert", json={"version": 1}).json()
    assert r["current_version"] == 4 and r["style_slug"] == "cercano" and r["versions"][0]["action"] == "revertir"


def test_manual_edit_with_unsourced_number_blocks_piece(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    piece = next(p for p in proposal["pieces"] if p["kind"] == "copy")
    segs = piece["content"]["segments"] + [{"text": "Además se taparon 9,999 baches extra.", "type": "opinion_marcada", "fact_ids": []}]
    r = client.put(f"/pieces/{piece['id']}/content", json={"segments": segs, "note": "agrego dato"}).json()
    assert r["status"] == "bloqueado" and any(f["code"] == "unsourced" for f in r["validation"])
    assert r["versions"][0]["author_type"] == "persona"


def test_red_team_notes_are_informative(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    piece = client.get(f"/pieces/{proposal['pieces'][0]['id']}").json()
    assert piece["red_team_notes"] and sum(piece["red_team_summary"].values()) == len(piece["red_team_notes"])
    assert any(b["factor"] == "red_team" and b["points"] > 0 for b in piece["risk_breakdown"])


def test_veda_blocks_generation_for_blocked_format(client, db):
    login(client)
    case = _ready_case(client, fmt="formato_titeres")
    veda = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == 1))
    veda.starts_at, veda.ends_at = utcnow() - timedelta(hours=1), utcnow() + timedelta(days=2)
    db.commit()
    r = client.post(f"/cases/{case['id']}/generate", json={})
    assert r.status_code == 409 and r.json()["error"]["details"]["rule_id"] == "HR-04"


def test_accusation_cannot_generate_before_legal(client):
    login(client)
    case = next(c for c in _cases(client, status="interpretado") if c["message_type"] == "acusacion_o_difamacion")
    d = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": _account(client, "formato_clasico")["id"]}).json()
    assert d["status"] == "revision_legal"
    assert client.post(f"/cases/{case['id']}/generate", json={}).status_code == 409


def test_preview_html_contains_sources_and_label(client):
    login(client)
    case = _ready_case(client, fmt="formato_voz_pueblo")
    proposal = _generate(client, case["id"])
    creative = next(p for p in proposal["pieces"] if p["kind"] == "creative" and p["creative_slug"] == "dato_duro")
    html = client.get(f"/pieces/{creative['id']}/preview").text
    assert "ILUSTRACIÓN REPRESENTATIVA" in html and "Fuente:" in html
