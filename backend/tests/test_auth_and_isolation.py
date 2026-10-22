from sqlalchemy import select

from app.models.core import AuditLog
from tests.conftest import login


def test_login_and_me(client):
    me = login(client)
    assert me["user"]["role"] == "analista"
    assert me["client"]["slug"] == "municipio-ejemplo"
    assert {c["slug"] for c in me["clients"]} == {"municipio-ejemplo", "candidatura-ejemplo"}
    assert "case.decide" in me["permissions"]
    assert "piece.approve" not in me["permissions"]


def test_bad_password(client):
    r = client.post("/auth/login", json={"email": "analista@demo.mx", "password": "nope-nope"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_unauthenticated(client):
    assert client.get("/auth/me").status_code == 401


def test_view_as_switches_role_and_is_audited(client, db):
    login(client)
    r = client.post("/auth/view-as", json={"role": "aprobador"})
    assert r.status_code == 200
    me = client.get("/auth/me").json()
    assert me["user"]["role"] == "aprobador"
    assert "piece.approve" in me["permissions"]
    r = client.post("/auth/view-as", json={"role": "analista", "kb_owner": True})
    assert client.get("/auth/me").json()["user"]["kb_owner"] is True
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.view_as")) is not None


def test_client_isolation(client):
    me = login(client, "candidatura@demo.mx")
    assert [c["slug"] for c in me["clients"]] == ["candidatura-ejemplo"]
    other_id = 1 if me["client"]["id"] != 1 else 2
    r = client.post("/auth/select-client", json={"client_id": other_id})
    assert r.status_code == 403
    r = client.get("/topics", headers={"X-Client-Id": str(other_id)})
    assert r.status_code == 403


def test_topics_are_per_client(client):
    login(client, "admin@demo.mx", "municipio-ejemplo")
    r = client.post("/topics", json={"slug": "alumbrado", "name": "Alumbrado", "keywords": ["luminaria"]})
    assert r.status_code == 201
    assert "alumbrado" in {t["slug"] for t in client.get("/topics").json()}
    login(client, "admin@demo.mx", "candidatura-ejemplo")
    assert "alumbrado" not in {t["slug"] for t in client.get("/topics").json()}


def test_settings_require_admin_and_are_audited(client):
    login(client)
    assert client.patch("/settings", json={"patch": {"baseline_min_days": 7}}).status_code == 403
    login(client, "admin@demo.mx")
    r = client.patch("/settings", json={"patch": {"alert_thresholds": {"medio": 2.0}}})
    assert r.status_code == 200
    s = r.json()["settings"]
    assert s["alert_thresholds"]["medio"] == 2.0 and s["alert_thresholds"]["alto"] == 3.0
    audit = client.get("/audit", params={"entity_type": "client_settings"}).json()
    assert audit["total"] >= 1
    assert audit["items"][0]["after"]["alert_thresholds"]["medio"] == 2.0


def test_admin_creates_client_with_bootstrap(client):
    login(client, "admin@demo.mx")
    r = client.post("/clients", json={"name": "Partido Azul Ejemplo", "slug": "partido-azul", "client_type": "partido"})
    assert r.status_code == 201
    cid = r.json()["id"]
    topics = client.get("/topics", headers={"X-Client-Id": str(cid)}).json()
    assert {t["slug"] for t in topics} >= {"baches", "agua"}


def test_hard_rules_endpoint(client):
    login(client)
    rules = client.get("/meta/hard-rules").json()
    assert [r["id"] for r in rules] == [f"HR-{i:02d}" for i in range(1, 12)]
