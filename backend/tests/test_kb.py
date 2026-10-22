import io

from app.services.documents import make_text_pdf
from tests.conftest import login


def test_facts_seeded_with_source_and_expiry(client):
    login(client)
    page = client.get("/kb/facts", params={"page_size": 200}).json()
    assert page["total"] >= 30
    facts = page["items"]
    with_doc = next(f for f in facts if f["document"])
    assert with_doc["source_label"].startswith(with_doc["code"]) and with_doc["document"]["title"] in with_doc["source_label"]
    assert any(f["expired"] for f in facts), "some facts are expired on purpose"
    no_doc = next(f for f in facts if not f["document"])
    assert "sin documento de origen" in no_doc["source_label"]
    expired = client.get("/kb/facts", params={"status": "vencido"}).json()
    assert expired["total"] >= 2 and all(f["expired"] for f in expired["items"])


def test_semantic_search_finds_relevant_content(client):
    login(client)
    hits = client.get("/kb/search", params={"q": "baches en la avenida central jurisdicción estatal"}).json()
    assert hits, "search returned nothing"
    top = " ".join(h["snippet"].lower() for h in hits[:4])
    assert "avenida central" in top or "estatal" in top
    hits = client.get("/kb/search", params={"q": "fugas de agua reparadas"}).json()
    assert any("fuga" in h["snippet"].lower() for h in hits[:3])


def test_only_kb_owner_curates_and_verifies(client):
    login(client)
    body = {"statement": "Dato de prueba con 10 unidades.", "value": 10, "unit": "unidades"}
    assert client.post("/kb/facts", json=body).status_code == 403
    client.post("/auth/view-as", json={"role": "analista", "kb_owner": True})
    r = client.post("/kb/facts", json=body)
    assert r.status_code == 201
    fact = r.json()
    assert fact["code"].startswith("H-") and fact["verified_at"] is None
    r = client.post(f"/kb/facts/{fact['id']}/verify")
    assert r.status_code == 200 and r.json()["verified_by_name"]
    r = client.patch(f"/kb/facts/{fact['id']}", json={"value": 11})
    assert r.json()["verified_at"] is None, "changing a fact invalidates its verification"


def test_csv_import_reports_row_errors(client):
    login(client, "base@demo.mx")
    csv_data = (
        "code,statement,value,unit,base,period_label,period_start,period_end,fact_date,document,gov_level,topic,valid_until,notes\n"
        ",Se instalaron 40 bebederos en escuelas.,40,bebederos,total,2026,2026-01-01,2026-12-31,,,municipio,agua,2027-12-31,\n"
        ",x,1,u,total,,,,,,,,,\n"
        ",Dato con tema inexistente para probar.,5,u,total,,,,,,,inexistente,,\n"
    )
    r = client.post("/kb/facts/import", files={"file": ("hechos.csv", csv_data.encode(), "text/csv")})
    assert r.status_code == 200
    report = r.json()
    assert report["created"] == 1 and len(report["errors"]) == 2


def test_pdf_upload_is_chunked_and_searchable(client):
    login(client, "base@demo.mx")
    pdf = make_text_pdf("Programa de bebederos escolares", ["Se instalarán bebederos de agua potable en todas las primarias del municipio durante el ciclo escolar."] * 5)
    r = client.post(
        "/kb/documents",
        data={"title": "Programa de bebederos escolares", "issuer": "Organismo Operador", "doc_type": "programa"},
        files={"file": ("bebederos.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    doc = client.get(f"/kb/documents/{r.json()['id']}").json()
    assert doc["status"] == "procesado" and doc["chunks"]
    hits = client.get("/kb/search", params={"q": "bebederos en primarias"}).json()
    assert hits[0]["kind"] == "chunk" and hits[0]["title"] == "Programa de bebederos escolares"
    bad = client.post("/kb/documents", data={"title": "x"}, files={"file": ("x.txt", b"hola", "text/plain")})
    assert bad.status_code == 422


def test_real_photo_requires_credit(client):
    login(client, "diseno@demo.mx")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, "PNG")
    r = client.post("/kb/images", data={"title": "Sin crédito", "image_type": "foto_real"}, files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 422
    r = client.post("/kb/images", data={"title": "Con crédito", "image_type": "foto_real", "credit": "Archivo"}, files={"file": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201
    key = r.json()["file_key"]
    assert client.get(f"/files/{key}").status_code == 200


def test_kb_is_isolated_per_client(client):
    login(client, "candidatura@demo.mx")
    facts = client.get("/kb/facts").json()["items"]
    assert facts and all("Municipio Ejemplo reparó" not in f["statement"] for f in facts)
    municipio_fact_id = 1
    assert client.get(f"/kb/facts/{municipio_fact_id}").status_code == 404


def test_actors_competences_history(client):
    login(client)
    actors = client.get("/kb/actors").json()
    estatal = next(a for a in actors if a["name"] == "Gobierno Estatal Ejemplo")
    assert "Gobierno del Estado" in estatal["aliases"]
    assert len(client.get("/kb/competences").json()) >= 12
    hist = client.get("/kb/history", params={"topic": "baches"}).json()
    assert len(hist) >= 7
    stats = client.get("/kb/stats").json()
    assert stats["images"] == 10 and stats["briefs"] == 4
