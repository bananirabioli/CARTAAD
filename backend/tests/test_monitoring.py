import io
from datetime import timedelta

from PIL import Image
from sqlalchemy import select

from app.db import utcnow
from app.models.monitoring import Comment, MonitoredSource, Post
from app.services.alert import add_snapshot, apply_alert, level_for_ratio, refresh_source_baseline
from app.services.client_settings import ClientSettings
from tests.conftest import login


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (200, 200, 230)).save(buf, "PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ alert rules


def test_alert_thresholds_are_configurable():
    s = ClientSettings()
    assert [level_for_ratio(r, s) for r in (1.0, 1.5, 2.9, 3.0, 5.9, 6.0, 20)] == ["bajo", "medio", "medio", "alto", "alto", "critico", "critico"]
    s2 = ClientSettings.model_validate({"alert_thresholds": {"medio": 2, "alto": 4, "critico": 8}})
    assert level_for_ratio(3.0, s2) == "medio" and level_for_ratio(7.9, s2) == "alto"


def test_seeded_posts_hit_their_alert_levels(db):
    posts = list(db.scalars(select(Post).where(Post.client_id == 1, Post.is_history.is_(False))))
    assert len(posts) == 43
    assert {p.alert_level for p in posts} == {"bajo", "medio", "alto", "critico", "sin_linea_base"}
    assert all(p.alert_level == p.meta["seed"]["alert"] for p in posts)


def test_velocity_window_and_insufficient_baseline(db):
    settings = ClientSettings()
    now = utcnow()
    src = MonitoredSource(client_id=1, name="Página nueva", network="facebook", source_type="pagina_ciudadana", priority="media")
    db.add(src)
    db.flush()
    post = Post(client_id=1, source_id=src.id, network="facebook", text="x", content_hash="h-test", published_at=now - timedelta(hours=10))
    post.source = src
    db.add(post)
    db.flush()
    add_snapshot(db, post, 10, 0, 0, now - timedelta(hours=8))
    add_snapshot(db, post, 100, 10, 10, now - timedelta(hours=6))
    add_snapshot(db, post, 400, 40, 40, now)
    result = apply_alert(post, settings, now)
    assert result.level == "sin_linea_base" and result.velocity == round((480 - 120) / 6, 2)
    src.baseline_per_hour, src.baseline_since = 10.0, now - timedelta(days=20)
    result = apply_alert(post, settings, now)
    assert result.level == "critico" and result.ratio == 6.0


def test_baseline_is_computed_from_snapshot_history(db):
    src = db.scalar(select(MonitoredSource).where(MonitoredSource.client_id == 1, MonitoredSource.name == "Vecinos Unidos Colonia Centro"))
    refresh_source_baseline(db, src)
    assert src.baseline_per_hour and src.baseline_per_hour >= 8.0
    assert (utcnow() - src.baseline_since).days >= 14


# ------------------------------------------------------------------ sources


def test_sources_filters_pagination_and_csv_import(client):
    login(client, "admin@demo.mx")
    page = client.get("/sources", params={"page_size": 5}).json()
    assert page["total"] == 12 and len(page["items"]) == 5
    assert all(s["network"] == "facebook" for s in client.get("/sources", params={"network": "facebook"}).json()["items"])
    rows = "name,network,handle,source_type,priority\n" + "\n".join(f"Página de prueba {i},facebook,@prueba{i},pagina_ciudadana,baja" for i in range(100))
    r = client.post("/sources/import", files={"file": ("fuentes.csv", rows.encode(), "text/csv")})
    assert r.json()["created"] == 100
    big = client.get("/sources", params={"q": "prueba", "page": 3, "page_size": 40}).json()
    assert big["total"] == 100 and len(big["items"]) == 20
    login(client)
    assert client.post("/sources", json={"name": "x", "network": "x", "source_type": "medio"}).status_code == 403


def test_check_source_runs_mock_adapter(client):
    login(client)
    src = client.get("/sources", params={"q": "Opinador"}).json()["items"][0]
    r = client.post(f"/sources/{src['id']}/check")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    assert r.json()["updated"] >= 1
    audit = client.get("/audit", params={"action": "source.check"}).json()
    assert audit["total"] >= 1


# ------------------------------------------------------------------ manual capture


def test_manual_capture_with_blur_and_dedupe(client, db):
    login(client)
    data = {"text": "Ojo @vecino.molesto: la fuga de la Colonia Centro lleva días sin atenderse.", "network": "facebook", "source_name": "Grupo vecinal nuevo", "blur_names": "true", "likes": "30", "comments": "5", "shares": "2", "comments_text": "Yo también la vi\nUrge"}
    r = client.post("/posts/manual", data=data, files={"image": ("captura.png", _png(), "image/png")})
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["origin"] == "manual" and post["names_blurred"] and post["image_key"]
    assert "@vecino.molesto" not in post["text"] and "[nombre]" in post["text"]
    assert "modo mock" in post["visual_context"]
    assert post["alert_level"] == "sin_linea_base" and len(post["comments"]) == 2
    assert client.get(f"/files/{post['image_key']}").status_code == 200
    src = db.scalar(select(MonitoredSource).where(MonitoredSource.name == "Grupo vecinal nuevo"))
    assert src and src.active is False
    again = client.post("/posts/manual", data=data).json()
    assert again["id"] == post["id"], "same publication is deduplicated"


def test_manual_capture_requires_text_or_image(client):
    login(client)
    assert client.post("/posts/manual", data={"text": "  ", "network": "x"}).status_code == 422
    login(client, "legal@demo.mx")
    assert client.post("/posts/manual", data={"text": "hola", "network": "x"}).status_code == 403


def test_comments_never_store_identities(db):
    from app.services.ingest import add_comments

    post = db.scalar(select(Post).where(Post.client_id == 1, Post.is_history.is_(False)))
    add_comments(db, post, [{"text": "Llámenme al 33 1234 5678, soy @juanito", "author": "Juan", "user_id": 99, "profile_url": "https://facebook.com/juan"}])
    db.flush()
    stored = db.scalars(select(Comment).where(Comment.post_id == post.id)).all()[-1]
    assert "juanito" not in stored.text and "1234" not in stored.text
    assert not hasattr(Comment, "author") and not hasattr(Comment, "user_id")


def test_file_import_adapter(client):
    login(client)
    csv_data = "source,network,text,likes,comments,shares,comments_text\n@diariodigitalej,x,Reportan bacheo nocturno en la Colonia Norte.,40,5,3,Bien|Ya era hora\n@desconocida,x,Texto,1,1,1,\n"
    r = client.post("/posts/import", files={"file": ("export.csv", csv_data.encode(), "text/csv")}).json()
    assert r["created"] == 1 and len(r["errors"]) == 1


def test_webhook_stub(client, monkeypatch):
    body = {"channel": "telegram", "client_slug": "municipio-ejemplo", "text": "Captura reenviada por el bot", "extra": {"sender": "+52 33 0000 0000"}}
    assert client.post("/ingest/webhook", json=body).status_code == 503
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "webhook_token", "secreto")
    assert client.post("/ingest/webhook", json=body, headers={"X-Webhook-Token": "mal"}).status_code == 401
    r = client.post("/ingest/webhook", json=body, headers={"X-Webhook-Token": "secreto"})
    assert r.status_code == 202 and r.json()["status"] == "recibido"


def test_posts_list_ordering(client):
    login(client)
    items = client.get("/posts", params={"order": "ratio", "page_size": 5}).json()["items"]
    assert items[0]["alert_level"] == "critico"


# ------------------------------------------------------------------ owned accounts


def test_accounts_one_per_format_and_registration(client):
    login(client, "admin@demo.mx")
    accounts = client.get("/accounts").json()
    own = [a for a in accounts if a["account_type"] == "propia" and a["registered"]]
    assert len({a["format_slug"] for a in own}) == 6
    pending = next(a for a in accounts if not a["registered"])
    assert client.post(f"/accounts/{pending['id']}/verify").status_code == 422
    assert client.post("/accounts", json={"network": "x", "handle": "@x", "display_name": "x", "account_type": "propia", "format_slug": "no_existe"}).status_code == 422
