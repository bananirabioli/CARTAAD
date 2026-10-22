"""Section 13: three seeded cases already advanced, in different states."""

from tests.conftest import login


def _by_status(client, status):
    return client.get("/cases", params={"status": status, "page_size": 50}).json()["items"]


def test_rated_case_with_measured_variants(client):
    login(client)
    rated = _by_status(client, "calificado")
    assert rated
    metrics = client.get(f"/cases/{rated[0]['id']}/metrics").json()
    assert metrics["rating"] == "funciono" and len(metrics["variants"]) == 2
    assert sum(1 for v in metrics["variants"] if v["winner"]) == 1


def test_case_in_review_has_style_variants_and_copilot_versions(client):
    login(client)
    case = _by_status(client, "en_revision")[0]
    proposal = client.get(f"/cases/{case['id']}/proposals").json()[0]
    copies = [p for p in proposal["pieces"] if p["kind"] == "copy"]
    assert len({p["style_slug"] for p in copies}) == 3
    edited = next(p for p in copies if p["current_version"] >= 3)
    versions = sorted(client.get(f"/pieces/{edited['id']}").json()["versions"], key=lambda v: v["version"])
    assert [v["action"] for v in versions][-2:] == ["mas_corto", "mas_empatico"]
    assert all(v["author_type"] == "ia" for v in versions[1:])


def test_flow_b_case_scheduled_with_ally_package(client):
    login(client, "aprobador@demo.mx")
    case = _by_status(client, "programado")[0]
    assert case["flow"] == "B"
    scheduled = [s for s in client.get("/schedule").json() if s["case_id"] == case["id"]]
    assert scheduled and scheduled[0]["status"] == "programado"
    packages = [p for p in client.get("/ally-packages").json() if p["case_id"] == case["id"]]
    assert packages and not packages[0]["revoked"]
