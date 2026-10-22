"""End-to-end acceptance tests (section 15): Flujo A and Flujo B through the API with the MockProvider."""

from datetime import timedelta

from app.db import utcnow
from tests.conftest import login


def _account(client, fmt, account_type="propia"):
    return next(a for a in client.get("/accounts").json() if a["format_slug"] == fmt and a["registered"] and a["account_type"] == account_type)


def _verify_and_approve(client, piece_id):
    piece = client.get(f"/pieces/{piece_id}").json()
    for f in piece["figures"]:
        assert client.post(f"/pieces/{piece_id}/figures/{f['id']}/verify", json={"status": "verificada"}).status_code == 200
    r = client.post(f"/pieces/{piece_id}/approve", json={"note": "revisado"})
    assert r.status_code == 200, r.json()
    return r.json()


def _publish(client, piece_id, account_id, copy_piece_id=None):
    r = client.post("/schedule", json={"piece_id": piece_id, "account_id": account_id, "copy_piece_id": copy_piece_id, "scheduled_at": (utcnow() + timedelta(hours=2)).isoformat()})
    assert r.status_code == 201, r.json()
    sp = r.json()
    assert client.post(f"/schedule/{sp['id']}/publish-now").json()["status"] == "publicado"
    return sp


def test_flujo_a_end_to_end(client):
    login(client)  # analista captures, decides and generates
    learning_before = client.get("/metrics/learning", params={"topic": "agua"}).json()["sample_size"]
    r = client.post("/posts/manual", data={
        "text": "El municipio no ha invertido nada en agua potable este año. Cero obras: la red se cae a pedazos.",
        "network": "facebook", "source_name": "Vecinos del Oriente", "likes": "120", "comments": "40", "shares": "35",
        "comments_text": "Fuente?\nEn mi calle sí cambiaron la tubería\nSiempre lo mismo",
    })
    assert r.status_code == 201
    case_id = r.json()["case_id"]
    case = client.get(f"/cases/{case_id}").json()
    assert case["status"] == "interpretado" and case["classification"]["stance"] == "en_contra" and case["flow"] == "A"
    assert case["classification"]["message_type"] == "dato_falso" and case["topic_slug"] == "agua"
    assert any(c["verdict"] == "falsa" and c["fact_ids"] for c in case["interpretation"]["claims"])
    assert case["strategy_suggested"] == "desmentir" and case["risk_score"] is not None

    account = _account(client, "formato_clasico")
    case = client.post(f"/cases/{case_id}/decide", json={"decision": "responder", "account_id": account["id"], "strategy": "desmentir", "style_slug": "cercano"}).json()
    assert case["status"] == "listo_para_generar" and case["style_slug"] == "cercano"

    proposal = client.post(f"/cases/{case_id}/generate", json={}).json()
    assert proposal["status"] == "listo"
    copies = [p for p in proposal["pieces"] if p["kind"] == "copy"]
    creatives = [p for p in proposal["pieces"] if p["kind"] == "creative"]
    assert len(copies) == 3 and 5 <= len(creatives) <= 10
    assert all(p["red_team_summary"] is not None for p in proposal["pieces"])
    copy_piece = next(p for p in copies if p["style_slug"] == "cercano")
    creative = next(p for p in creatives if p["creative_slug"] == "dato_duro")
    assert copy_piece["validation_status"] != "block" and creative["validation_status"] != "block"

    login(client, "aprobador@demo.mx")  # verifies every figure and approves
    assert _verify_and_approve(client, copy_piece["id"])["status"] == "aprobado"
    assert _verify_and_approve(client, creative["id"])["status"] == "aprobado"
    assert client.get(f"/cases/{case_id}").json()["status"] == "aprobado"

    sp = _publish(client, creative["id"], account["id"], copy_piece["id"])
    assert "Fuentes:" in sp["text"]
    assert client.get(f"/cases/{case_id}").json()["status"] == "publicado"

    login(client)  # analista records metrics and rates
    r = client.post(f"/cases/{case_id}/metrics", json={"piece_id": creative["id"], "reach": 5400, "impressions": 8000, "likes": 300, "comments": 40, "shares": 90,
                                                       "sentiment_pos": 0.4, "sentiment_neg": 0.2, "sentiment_neu": 0.4})
    assert r.status_code == 200 and r.json()["status"] == "medido" and r.json()["variants"][0]["reach_ratio"]
    r = client.post(f"/cases/{case_id}/rate", json={"outcome": "funciono", "note": "Bajó el tono de los comentarios."})
    assert r.json()["status"] == "calificado" and r.json()["rating"] == "funciono"
    assert client.get("/metrics/learning", params={"topic": "agua"}).json()["sample_size"] == learning_before + 1, "rating feeds the learning context"


def test_flujo_b_end_to_end(client):
    login(client)
    r = client.post("/posts/manual", data={
        "text": "Gracias por rehabilitar el parque de la Colonia Oriente: quedó muy bien y por fin los niños tienen dónde jugar.",
        "network": "instagram", "source_name": "Vecinas del Oriente", "likes": "300", "comments": "25", "shares": "60",
    })
    case_id = r.json()["case_id"]
    case = client.get(f"/cases/{case_id}").json()
    assert case["classification"]["stance"] == "a_favor" and case["flow"] == "B" and case["strategy_suggested"] in ("amplificar", "agradecer")

    account = _account(client, "formato_clasico")
    case = client.post(f"/cases/{case_id}/decide", json={"decision": "responder", "account_id": account["id"]}).json()
    assert case["status"] == "listo_para_generar"
    proposal = client.post(f"/cases/{case_id}/generate", json={}).json()
    creatives = [p for p in proposal["pieces"] if p["kind"] == "creative"]
    assert creatives and {p["creative_slug"] for p in creatives} <= {"repost_contexto", "agradecimiento", "lo_que_no_se_vio", "guion_dueto", "carrusel_resultados", "pieza_aliados"}
    assert all("flujo:B" in p["effective_tags"] for p in proposal["pieces"])
    ally_piece = next(p for p in creatives if p["creative_slug"] == "pieza_aliados")
    copy_piece = next(p for p in proposal["pieces"] if p["kind"] == "copy" and p["validation_status"] != "block")

    login(client, "aprobador@demo.mx")
    _verify_and_approve(client, ally_piece["id"])
    _verify_and_approve(client, copy_piece["id"])
    pkg = client.post("/ally-packages", json={"case_id": case_id, "title": "Reconocimiento al parque", "piece_ids": [ally_piece["id"], copy_piece["id"]]}).json()
    assert client.get(f"/public/ally/{pkg['token']}").status_code == 200
    _publish(client, ally_piece["id"], account["id"], copy_piece["id"])

    r = client.post(f"/cases/{case_id}/metrics/simulate").json()
    assert r["status"] == "medido" and r["variants"]
    assert client.post(f"/cases/{case_id}/rate", json={"outcome": "funciono"}).json()["status"] == "calificado"
    rankings = client.get("/metrics/rankings", params={"topic": "obra_publica"}).json()
    assert rankings["sample_size"] >= 5 and rankings["styles"]
