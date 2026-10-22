from tests.conftest import login
from tests.test_publishing import _approvable_copy, _proposal, _verify_all


def _published_case(client):
    case, proposal = _proposal(client)
    pieces = [_approvable_copy(client, proposal), next(p for p in proposal["pieces"] if p["creative_slug"] == "dato_duro")]
    login(client, "aprobador@demo.mx")
    account = case["account_id"]
    for p in pieces:
        _verify_all(client, p["id"])
        assert client.post(f"/pieces/{p['id']}/approve", json={}).status_code == 200
        sp = client.post("/schedule", json={"piece_id": p["id"], "account_id": account, "scheduled_at": "2030-01-01T10:00:00Z"}).json()
        assert client.post(f"/schedule/{sp['id']}/publish-now").json()["status"] == "publicado"
    return case, pieces


def test_metrics_only_for_published_pieces(client):
    case, proposal = _proposal(client)
    piece = _approvable_copy(client, proposal)
    r = client.post(f"/cases/{case['id']}/metrics", json={"piece_id": piece["id"], "reach": 100})
    assert r.status_code == 409


def test_rating_requires_metrics(client):
    case, _ = _published_case(client)
    assert client.post(f"/cases/{case['id']}/rate", json={"outcome": "funciono"}).status_code == 409


def test_ab_comparison_marks_one_winner_and_rating_writes_history(client):
    case, pieces = _published_case(client)
    login(client)
    client.post(f"/cases/{case['id']}/metrics", json={"piece_id": pieces[0]["id"], "reach": 1000, "sentiment_neg": 0.5})
    r = client.post(f"/cases/{case['id']}/metrics", json={"piece_id": pieces[1]["id"], "reach": 9000, "sentiment_neg": 0.1}).json()
    winners = [v for v in r["variants"] if v["winner"]]
    assert len(r["variants"]) == 2 and len(winners) == 1 and winners[0]["piece_id"] == pieces[1]["id"]
    before = client.get("/metrics/rankings").json()["sample_size"]
    r = client.post(f"/cases/{case['id']}/rate", json={"outcome": "no_funciono", "note": "poca tracción"}).json()
    assert r["status"] == "calificado"
    after = client.get("/metrics/rankings").json()
    assert after["sample_size"] == before + 2, "one ResponseHistory row per measured variant"


def test_rankings_flag_insufficient_samples(client):
    login(client)
    data = client.get("/metrics/rankings").json()
    assert data["min_sample"] >= 1
    for row in data["styles"]:
        assert row["sufficient"] == (row["n"] >= data["min_sample"])
