import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models  # noqa: F401
from app.api import admin, auth, files, kb
from app.config import get_settings
from app.errors import install_handlers

logger = logging.getLogger("cartaad")

ROUTERS = [auth.router, admin.router, files.router, kb.router]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if get_settings().auto_seed:
        from app.seed.seed import seed_if_empty

        try:
            seed_if_empty()
        except Exception:  # noqa: BLE001
            logger.exception("seed failed")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="C-A-R-T-A-A-D API",
        version="0.1.0",
        description="Centro de Alerta y Respuesta Temprana a Amenazas Digitales · prototipo beta",
        lifespan=lifespan,
    )
    install_handlers(app)
    for router in ROUTERS:
        app.include_router(router)

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        s = get_settings()
        return {"status": "ok", "llm_provider": s.llm_provider, "renderer": s.renderer}

    return app


app = create_app()
