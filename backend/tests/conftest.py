import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="cartaad-tests-"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_TMP / 'boot.db'}",
        "AUTO_SEED": "false",
        "PASSWORD_ITERATIONS": "1000",
        "CELERY_EAGER": "true",
        "STORAGE_DIR": str(_TMP / "files"),
        "RENDERER": "pillow",
        "LLM_PROVIDER": "mock",
        "DEMO_MODE": "true",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as app_db  # noqa: E402
from app.db import Base, SessionLocal, configure_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.seed import DEMO_PASSWORD, run_seed  # noqa: E402


@pytest.fixture(scope="session")
def template_db() -> Path:
    path = _TMP / "template.db"
    configure_engine(f"sqlite:///{path}")
    Base.metadata.create_all(app_db.engine)
    with SessionLocal() as session:
        run_seed(session)
    app_db.engine.dispose()
    return path


@pytest.fixture
def db_path(template_db: Path, tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    shutil.copy(template_db, path)
    configure_engine(f"sqlite:///{path}")
    yield path
    app_db.engine.dispose()


@pytest.fixture
def db(db_path: Path):
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_path: Path) -> TestClient:
    with TestClient(app) as c:
        yield c


def login(c: TestClient, email: str = "analista@demo.mx", client_slug: str | None = None) -> dict:
    r = c.post("/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    if client_slug:
        me = c.get("/auth/me").json()
        target = next(cl for cl in me["clients"] if cl["slug"] == client_slug)
        assert c.post("/auth/select-client", json={"client_id": target["id"]}).status_code == 200
    return c.get("/auth/me").json()


@pytest.fixture
def as_role(client: TestClient):
    def _as(email: str, client_slug: str | None = None) -> TestClient:
        login(client, email, client_slug)
        return client

    return _as
