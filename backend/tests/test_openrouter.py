"""MVP: OpenRouter provider (HTTP mocked), single-call analysis, content generation and the production seed."""

import base64

import httpx
import pytest
from sqlalchemy import select

from app.ai import openrouter
from app.ai.provider import LLMRequest, ProviderError
from app.ai.steps import AnalyzeCaptureOut, ClassifyOut
from app.config import get_settings
from tests.conftest import login


class _Resp:
    def __init__(self, status: int = 200, payload: dict | None = None, content: bytes = b"", headers: dict | None = None):
        self.status_code, self._payload, self.content, self.headers, self.text = status, payload or {}, content, headers or {}, str(payload)

    def json(self) -> dict:
        return self._payload


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "sk-or-test")
    monkeypatch.setattr(get_settings(), "video_poll_seconds", 0)


def _req(step: str = "classify", model=ClassifyOut, image=None) -> LLMRequest:
    return LLMRequest(step=step, system="sys", prompt="hola", context={}, output_model=model, image=image)


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(get_settings(), "openrouter_api_key", None)
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        openrouter.OpenRouterProvider().complete(_req())


def test_provider_sends_schema_image_and_parses_json(monkeypatch, key):
    sent = {}

    def fake(method, url, **kw):
        sent.update(kw["json"], url=url, auth=kw["headers"]["Authorization"])
        return _Resp(payload={"choices": [{"finish_reason": "stop", "message": {"content": '```json\n{"stance": "en_contra", "topic": "otro", "message_type": "opinion", '
                                                                                      '"recommendation": "monitorear", "confidence": 0.7, "explanation": "x", "canalizar_a_atencion": false}\n```'}}]})

    monkeypatch.setattr(httpx, "request", fake)
    out = openrouter.OpenRouterProvider().complete(_req("analyze_capture", ClassifyOut, image=(b"png", "image/png")))
    assert out["stance"] == "en_contra"
    assert sent["url"].endswith("/chat/completions") and sent["auth"] == "Bearer sk-or-test"
    assert sent["model"] == get_settings().openrouter_model_analysis
    schema = sent["response_format"]["json_schema"]["schema"]
    assert schema["additionalProperties"] is False and set(schema["required"]) == set(schema["properties"])
    assert "minimum" not in str(schema)
    assert sent["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_strict_schema_handles_nested_models():
    schema = openrouter._strict_schema(AnalyzeCaptureOut.model_json_schema())
    for sub in schema["$defs"].values():
        if sub.get("type") == "object":
            assert sub["additionalProperties"] is False


@pytest.mark.parametrize(("status", "msg"), [(401, "API key"), (402, "créditos"), (429, "límite"), (500, "500")])
def test_http_errors_become_spanish_messages(monkeypatch, key, status, msg):
    monkeypatch.setattr(httpx, "request", lambda *a, **k: _Resp(status, {"error": {"message": "boom"}}))
    with pytest.raises(ProviderError, match=msg):
        openrouter.OpenRouterProvider().complete(_req())


def test_image_from_data_url(monkeypatch, key):
    png = b"\x89PNG fake"
    url = "data:image/png;base64," + base64.b64encode(png).decode()
    monkeypatch.setattr(httpx, "request", lambda *a, **k: _Resp(payload={"choices": [{"message": {"images": [{"image_url": {"url": url}}]}}]}))
    data, mime = openrouter.generate_image("A calm street at sunset", "4:5")
    assert data == png and mime == "image/png"


def test_video_submit_poll_download(monkeypatch, key):
    calls = []

    def fake(method, url, **kw):
        calls.append((method, url))
        if method == "POST":
            assert kw["json"]["duration"] == 6 and kw["json"]["aspect_ratio"] == "9:16"
            return _Resp(payload={"id": "job1", "status": "pending", "polling_url": "/api/v1/videos/job1"})
        if url.endswith("/content?index=0"):
            return _Resp(content=b"MP4")
        n = sum(1 for c in calls if c[0] == "GET")
        return _Resp(payload={"id": "job1", "status": "completed" if n >= 2 else "in_progress", "polling_url": "/api/v1/videos/job1"})

    monkeypatch.setattr(httpx, "request", fake)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(payload={"data": [{"id": get_settings().openrouter_model_video, "supported_durations": [4, 6, 8]}]}))
    data, meta = openrouter.generate_video("Slow dolly-in on a street", aspect_ratio="9:16", duration=7)
    assert data == b"MP4" and meta["job_id"] == "job1" and meta["duration"] == 6


def test_video_failure_is_reported(monkeypatch, key):
    monkeypatch.setattr(httpx, "request", lambda m, u, **k: _Resp(payload={"id": "j", "status": "failed", "error": "nsfw"}))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(payload={"data": []}))
    with pytest.raises(ProviderError, match="failed"):
        openrouter.generate_video("x")


# ------------------------------------------------------------------ MVP flow (mock provider answering the new steps)


@pytest.fixture
def single(monkeypatch):
    import app.services.capture as capture
    import app.services.cases as cases

    monkeypatch.setattr(capture, "single_analysis", lambda: True)
    monkeypatch.setattr(cases, "single_analysis", lambda: True)


def test_capture_analyze_and_generate_content(client, single):
    login(client)
    r = client.post("/posts/manual", data={"text": "El municipio no ha invertido nada en agua potable este año. Cero obras.", "network": "facebook"})
    assert r.status_code == 201, r.text
    case = client.get(f"/cases/{r.json()['case_id']}").json()
    assert case["status"] == "interpretado" and case["classification"]["stance"] == "en_contra"
    assert case["interpretation"]["summary"] and case["strategy_suggested"]

    r = client.post(f"/cases/{case['id']}/generate-content", json={"strategy": "contextualizar", "network": "facebook", "image_count": 1, "video": True})
    assert r.status_code == 202, r.text
    proposal = r.json()
    assert proposal["status"] == "listo" and proposal["options"]["mode"] == "content"
    kinds = [p["kind"] for p in proposal["pieces"]]
    assert kinds.count("copy") == 3 and kinds.count("image") == 1 and kinds.count("video") == 1
    image = next(p for p in proposal["pieces"] if p["kind"] == "image")
    assert image["render_status"] == "listo" and image["renders"] and image["content"]["meta"]["no_es_evidencia"]
    video = next(p for p in proposal["pieces"] if p["kind"] == "video")
    assert video["render_status"] == "no_aplica" and video["content"]["prompt"] and video["content"]["voiceover"]
    assert client.get(f"/cases/{case['id']}").json()["status"] == "generado"


def test_neutral_case_can_still_generate(client, single):
    login(client)
    r = client.post("/posts/manual", data={"text": "Hoy hay feria en la plaza principal.", "network": "facebook"})
    case = client.get(f"/cases/{r.json()['case_id']}").json()
    assert case["status"] == "monitoreando"
    r = client.post(f"/cases/{case['id']}/generate-content", json={"strategy": "amplificar", "image_count": 0})
    assert r.status_code == 202, r.text
    assert [p["kind"] for p in r.json()["pieces"]].count("copy") == 3


def test_image_prompt_sanitizer_falls_back():
    from app.services.content import safe_visual_prompt

    prompt, negative = safe_visual_prompt("A billboard with the text VOTE 2027 and a logo", "", "Soft illustration of a park")
    assert "logo" not in prompt.lower() and "2027" not in prompt and negative


# ------------------------------------------------------------------ production seed


def test_production_seed(db, monkeypatch):
    from app.models.core import Client, Topic, User
    from app.models.monitoring import OwnedAccount
    from app.seed import production

    for model in (Client, User):
        for row in db.scalars(select(model)):
            db.delete(row)
    db.commit()
    s = get_settings()
    monkeypatch.setattr(s, "demo_mode", False)
    monkeypatch.setattr(s, "admin_email", "Maestro@Example.com")
    monkeypatch.setattr(s, "admin_password", "una-contraseña-larga")
    production.seed_production(db)
    clients = list(db.scalars(select(Client)))
    assert [c.name for c in clients] == ["Candidatura Juárez"] and clients[0].settings["context"] == "Juárez, Chihuahua"
    assert not list(db.scalars(select(Topic).where(Topic.client_id == clients[0].id)))
    user = db.scalar(select(User))
    assert user.email == "maestro@example.com" and user.role == "owner"
    account = db.scalar(select(OwnedAccount).where(OwnedAccount.client_id == clients[0].id))
    assert account.registered and account.verified and account.account_type == "propia"
