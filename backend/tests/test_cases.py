from sqlalchemy import select

from app.models.cases import Case
from tests.conftest import login


def _case(client, **filters):
    items = client.get("/cases", params={"page_size": 200, **filters}).json()["items"]
    return items


def _account(client, fmt="formato_clasico", registered=True):
    return next(a for a in client.get("/accounts").json() if a["format_slug"] == fmt and a["registered"] == registered and a["account_type"] == "propia")


def test_seeded_cases_and_neutral_auto_monitor(client, db):
    login(client)
    cases = _case(client)
    assert len(cases) == 43
    neutral = [c for c in cases if c["stance"] == "neutral"]
    assert neutral and all(c["status"] == "monitoreando" for c in neutral)
    assert all(c["flow"] == "A" for c in cases if c["stance"] == "en_contra")
    assert all(c["flow"] == "B" for c in cases if c["stance"] == "a_favor")
    complaints = [c for c in cases if c["message_type"] == "queja_ciudadana_legitima"]
    assert complaints and all(c["canalizar_a_atencion"] for c in complaints), "HR-05: complaints are routed"
    accusations = [c for c in cases if c["message_type"] == "acusacion_o_difamacion"]
    assert accusations and all(c["legal_required"] and c["legal_status"] == "pendiente" for c in accusations)


def test_manual_capture_runs_full_pipeline(client):
    login(client)
    r = client.post("/posts/manual", data={"text": "Nunca han invertido en agua potable: no ha invertido ni un peso este año.", "network": "facebook", "source_name": "Página vecinal"})
    post = r.json()
    assert post["case_id"]
    case = client.get(f"/cases/{post['case_id']}").json()
    assert case["status"] == "interpretado" and case["classification"]["message_type"] == "dato_falso"
    assert case["strategy_suggested"] == "desmentir" and case["strategy_justification"]
    assert any(c["verdict"] == "falsa" and c["fact_ids"] for c in case["interpretation"]["claims"])
    assert case["risk_score"] is not None and len(case["risk_breakdown"]) == 7
    assert sum(f["points"] for f in case["risk_breakdown"]) > 0
    assert any(t["action"] == "case.transition" for t in case["timeline"])
    assert case["facts"] and case["facts"][0]["source_label"]


def test_decide_respond_uses_account_style_precedence(client):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "dato_falso")
    acc = _account(client, "formato_clasico")  # @CronicaMunicipal: account default = institucional (beats format default periodistico)
    r = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": acc["id"]})
    d = r.json()
    assert r.status_code == 200 and d["status"] == "listo_para_generar"
    assert d["style_slug"] == "institucional" and d["style_choice"]["source"] == "cuenta"
    assert d["strategy"] == case["strategy_suggested"]


def test_decide_respond_rejects_unregistered_account_and_bad_style(client):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "dato_falso")
    bad = _account(client, "formato_clasico", registered=False)
    r = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": bad["id"]})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-02"
    titeres = _account(client, "formato_titeres")
    r = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": titeres["id"], "style_slug": "institucional"})
    assert r.status_code == 422


def test_complaint_cannot_be_treated_as_attack(client):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "queja_ciudadana_legitima")
    acc = _account(client, "formato_clasico")
    r = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "strategy": "desmentir", "account_id": acc["id"]})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-05"
    r = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": acc["id"]})
    assert r.json()["strategy"] == "contextualizar" and r.json()["style_slug"] == "empatico"


def test_accusation_goes_to_legal_before_generation(client):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "acusacion_o_difamacion")
    acc = _account(client, "formato_clasico")
    d = client.post(f"/cases/{case['id']}/decide", json={"decision": "responder", "account_id": acc["id"]}).json()
    assert d["status"] == "revision_legal"
    assert client.post(f"/cases/{case['id']}/legal", json={"action": "liberar", "note": "ok"}).status_code == 403
    login(client, "legal@demo.mx")
    d = client.post(f"/cases/{case['id']}/legal", json={"action": "liberar", "note": "Se puede responder con datos, sin repetir la acusación."}).json()
    assert d["status"] == "listo_para_generar" and d["legal_status"] == "liberada"


def test_legal_can_block(client):
    login(client)
    cases = [c for c in _case(client, status="interpretado") if c["message_type"] == "acusacion_o_difamacion"]
    acc = _account(client, "formato_clasico")
    client.post(f"/cases/{cases[-1]['id']}/decide", json={"decision": "responder", "account_id": acc["id"]})
    login(client, "legal@demo.mx")
    d = client.post(f"/cases/{cases[-1]['id']}/legal", json={"action": "bloquear", "note": "Riesgo de difamación; no responder."}).json()
    assert d["status"] == "descartado" and "legal" in d["closed_reason"].lower()


def test_closing_requires_reason_and_can_reopen(client):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "opinion")
    assert client.post(f"/cases/{case['id']}/decide", json={"decision": "ignorar"}).status_code == 422
    d = client.post(f"/cases/{case['id']}/decide", json={"decision": "ignorar", "reason": "Bajo alcance; responder lo amplificaría."}).json()
    assert d["status"] == "ignorado"
    d = client.post(f"/cases/{case['id']}/reopen", json={"reason": "volvió a crecer"}).json()
    assert d["status"] == "interpretado"
    login(client, "legal@demo.mx")
    assert client.post(f"/cases/{case['id']}/decide", json={"decision": "ignorar", "reason": "x x x"}).status_code == 403


def test_editing_classification_recomputes_flow_and_legal(client, db):
    login(client)
    case = next(c for c in _case(client, status="interpretado") if c["message_type"] == "opinion" and c["stance"] == "en_contra")
    d = client.patch(f"/cases/{case['id']}/classification", json={"message_type": "acusacion_o_difamacion"}).json()
    assert d["legal_required"] and d["classification"]["edited_at"]
    d = client.patch(f"/cases/{case['id']}/classification", json={"stance": "a_favor", "message_type": "opinion"}).json()
    assert d["flow"] == "B" and not d["legal_required"] and d["strategy_suggested"] in ("amplificar", "agradecer")


def test_recommended_style_uses_learning_with_sample_size(client):
    login(client)
    baches = next(c for c in _case(client, topic="baches", status="interpretado") if c["flow"] == "A" and c["message_type"] != "queja_ciudadana_legitima")
    d = client.get(f"/cases/{baches['id']}").json()
    assert d["recommended_style"]["value"] == "cercano" and "5 de 7" in d["recommended_style"]["reason"]
    agua = next(c for c in _case(client, topic="agua", status="interpretado") if c["message_type"] in ("dato_falso", "opinion"))
    d = client.get(f"/cases/{agua['id']}").json()
    assert d["learning_context"]["sample_size"] == 6
    assert d["recommended_style"]["value"] is None and "insuficiente" in d["recommended_style"]["reason"].lower()


def test_coordinated_posts_are_flagged_as_repeated(client):
    login(client)
    d = client.get("/dashboard").json()
    assert d["repeated"] and d["repeated"][0]["count"] >= 3
    assert d["accelerating"][0]["alert_level"] == "critico"
    assert d["pending"]["decide"] > 0 and sum(d["by_alert"].values()) > 0


def test_cases_isolated_between_clients(client, db):
    other = db.scalar(select(Case).where(Case.client_id == 2))
    login(client)
    assert client.get(f"/cases/{other.id}").status_code == 404
