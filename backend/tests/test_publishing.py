import io
import zipfile
from datetime import timedelta

from sqlalchemy import select

from app.db import utcnow
from app.models.ops import RestrictionMode
from tests.conftest import login
from tests.test_generation import _account, _generate, _ready_case


def _verify_all(client, piece_id):
    piece = client.get(f"/pieces/{piece_id}").json()
    for f in piece["figures"]:
        client.post(f"/pieces/{piece_id}/figures/{f['id']}/verify", json={"status": "verificada"})
    return client.get(f"/pieces/{piece_id}").json()


def _proposal(client, fmt="formato_clasico"):
    login(client)
    case = _ready_case(client, fmt=fmt)
    return case, _generate(client, case["id"])


def _approvable_copy(client, proposal):
    """A copy variant without blocking findings (formato_clasico requires the D-003 legend, which the system adds)."""
    return next(p for p in proposal["pieces"] if p["kind"] == "copy" and p["validation_status"] != "block")


def test_approval_requires_every_figure_verified(client):
    case, proposal = _proposal(client)
    piece = _approvable_copy(client, proposal)
    login(client, "aprobador@demo.mx")
    r = client.post(f"/pieces/{piece['id']}/approve", json={})
    assert r.status_code == 409 and r.json()["error"]["details"]["rule_id"] == "HR-09"
    _verify_all(client, piece["id"])
    r = client.post(f"/pieces/{piece['id']}/approve", json={})
    assert r.status_code == 200 and r.json()["status"] == "aprobado" and r.json()["approved_version"] == r.json()["current_version"]
    assert client.get(f"/cases/{case['id']}").json()["status"] == "aprobado"
    login(client)
    assert client.post(f"/pieces/{piece['id']}/approve", json={}).status_code == 403


def test_copilot_after_approval_invalidates_it_and_blocks_scheduling(client):
    case, proposal = _proposal(client)
    piece = _approvable_copy(client, proposal)
    login(client, "aprobador@demo.mx")
    _verify_all(client, piece["id"])
    client.post(f"/pieces/{piece['id']}/approve", json={})
    r = client.post(f"/pieces/{piece['id']}/copilot", json={"action": "mas_corto"}).json()
    assert r["applied"] and r["piece"]["status"] == "generado" and r["piece"]["approved_version"] != r["piece"]["current_version"]
    acc = _account(client, "formato_clasico")
    r = client.post("/schedule", json={"piece_id": piece["id"], "account_id": acc["id"], "scheduled_at": (utcnow() + timedelta(hours=2)).isoformat()})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-09"


def _approved(client, fmt="formato_clasico"):
    case, proposal = _proposal(client, fmt)
    piece = _approvable_copy(client, proposal)
    login(client, "aprobador@demo.mx")
    _verify_all(client, piece["id"])
    assert client.post(f"/pieces/{piece['id']}/approve", json={}).status_code == 200
    return case, piece


def test_schedule_only_to_registered_accounts_and_publish(client):
    case, piece = _approved(client)
    bad = next(a for a in client.get("/accounts").json() if not a["registered"])
    when = (utcnow() + timedelta(hours=1)).isoformat()
    r = client.post("/schedule", json={"piece_id": piece["id"], "account_id": bad["id"], "scheduled_at": when})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-02"
    acc = _account(client, "formato_clasico")
    r = client.post("/schedule", json={"piece_id": piece["id"], "account_id": acc["id"], "scheduled_at": when})
    assert r.status_code == 201
    sp = r.json()
    assert "Fuentes:" in sp["text"], "HR-01: the outgoing text carries its sources"
    assert client.get(f"/cases/{case['id']}").json()["status"] == "programado"
    r = client.post(f"/schedule/{sp['id']}/publish-now").json()
    assert r["status"] == "publicado"
    assert client.get(f"/cases/{case['id']}").json()["status"] == "publicado"


def test_veda_blocks_scheduling_of_restricted_format(client, db):
    case, proposal = _proposal(client, "formato_comparativa")
    piece = _approvable_copy(client, proposal)
    login(client, "aprobador@demo.mx")
    _verify_all(client, piece["id"])
    assert client.post(f"/pieces/{piece['id']}/approve", json={}).status_code == 200
    veda = db.scalar(select(RestrictionMode).where(RestrictionMode.client_id == 1))
    acc = _account(client, "formato_comparativa")
    when = veda.starts_at + timedelta(days=1)
    r = client.post("/schedule", json={"piece_id": piece["id"], "account_id": acc["id"], "scheduled_at": when.isoformat()})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-04"


def test_due_posts_are_published_by_the_task(client, db):
    from app.services.publishing import publish_due

    case, piece = _approved(client)
    acc = _account(client, "formato_clasico")
    sp = client.post("/schedule", json={"piece_id": piece["id"], "account_id": acc["id"], "scheduled_at": (utcnow() + timedelta(minutes=5)).isoformat()}).json()
    db.expire_all()
    assert publish_due(db, utcnow() + timedelta(minutes=10)) == 1
    db.commit()
    assert next(s for s in client.get("/schedule").json() if s["id"] == sp["id"])["status"] == "publicado"


def test_ally_package_public_page_and_shares(client):
    case, piece = _approved(client)
    r = client.post("/ally-packages", json={"case_id": case["id"], "title": "Paquete baches", "message": "Gracias por compartir", "piece_ids": [piece["id"]], "expires_in_days": 3})
    assert r.status_code == 201
    pkg = r.json()
    client.post("/auth/logout")
    public = client.get(f"/public/ally/{pkg['token']}").json()
    assert public["pieces"] and public["accounts"] and all(a["type"] in ("aliada", "voceria") for a in public["accounts"])
    ally = public["accounts"][0]
    assert client.post(f"/public/ally/{pkg['token']}/shared", json={"account_id": ally["id"], "shared_by_name": "Colectivo"}).status_code == 200
    login(client)
    own = _account(client, "formato_clasico")
    client.post("/auth/logout")
    r = client.post(f"/public/ally/{pkg['token']}/shared", json={"account_id": own["id"], "shared_by_name": "x y"})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-02"
    z = client.get(f"/public/ally/{pkg['token']}/download.zip")
    assert z.status_code == 200 and zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    login(client, "aprobador@demo.mx")
    assert client.get("/ally-packages").json()[0]["shares"][0]["by"] == "Colectivo"
    client.post(f"/ally-packages/{pkg['id']}/revoke")
    assert client.get(f"/public/ally/{pkg['token']}").status_code == 404


def test_ally_package_rejects_unapproved_pieces(client):
    case, proposal = _proposal(client)
    login(client, "aprobador@demo.mx")
    r = client.post("/ally-packages", json={"case_id": case["id"], "title": "Paquete", "piece_ids": [proposal["pieces"][0]["id"]]})
    assert r.status_code == 422 and r.json()["error"]["rule_id"] == "HR-09"


def test_export_contains_png_copy_and_spec(client):
    login(client)
    case = _ready_case(client)
    proposal = _generate(client, case["id"])
    creative = next(p for p in proposal["pieces"] if p["kind"] == "creative" and p["creative_slug"] == "dato_duro")
    login(client, "aprobador@demo.mx")
    _verify_all(client, creative["id"])
    r = client.post(f"/pieces/{creative['id']}/approve", json={})
    assert r.status_code == 200, r.json()
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/pieces/{creative['id']}/export.zip").content))
    names = z.namelist()
    assert any(n.endswith("spec.json") for n in names) and any(n.endswith(".png") for n in names) and any(n.endswith("copy.txt") for n in names)
    spec = z.read(next(n for n in names if n.endswith("spec.json"))).decode()
    assert '"style"' in spec and '"effective_tags"' in spec


def test_inbox_filters_by_style_and_tag(client):
    _proposal(client)
    items = client.get("/inbox", params={"style": "cercano"}).json()["items"]
    assert items and all(i["style_slug"] == "cercano" for i in items)
    tagged = client.get("/inbox", params={"tag": "estrategia:contextualizar"}).json()["items"]
    assert tagged and all("estrategia:contextualizar" in i["effective_tags"] for i in tagged)
