from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
SCHEMAS_DIR = REPO_ROOT / "schemas"
FIXTURES_DIR = REPO_ROOT / "fixtures"
EVALS_DIR = REPO_ROOT / "evals"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"), extra="ignore")

    env: str = "dev"
    database_url: str = f"sqlite:///{BACKEND_DIR / 'cartaad.db'}"
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = True

    secret_key: str = "dev-secret-change-me"
    session_max_age: int = 60 * 60 * 24 * 7
    cookie_secure: bool = False
    password_iterations: int = 120_000

    demo_mode: bool = True
    auto_seed: bool = True

    llm_provider: str = "mock"  # mock | anthropic | openrouter
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    llm_max_tokens: int = 4096

    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Defaults checked against /api/v1/models and /api/v1/videos/models (2026-10-31); override per env.
    openrouter_model_analysis: str = "anthropic/claude-sonnet-5.5"  # needs vision + structured outputs
    openrouter_model_text: str = "anthropic/claude-sonnet-5.5"
    openrouter_model_image: str = "google/gemini-3.1-flash-image"
    openrouter_model_video: str = "google/veo-3.1-lite"  # 4/6/8 s, 9:16, ~0.03 USD/s at 720p without audio
    openrouter_video_resolution: str = "720p"
    openrouter_app_url: str = "https://cartaad.app"
    video_provider: str = "none"  # none | openrouter
    video_max_seconds: int = 6
    video_poll_seconds: int = 10
    video_timeout_seconds: int = 900

    # MVP master user, created by the production seed (DEMO_MODE=false)
    admin_email: str | None = None
    admin_password: str | None = None
    admin_name: str = "Administrador"
    initial_client_name: str = "Candidatura Juárez"
    initial_client_context: str = "Juárez, Chihuahua"

    embedding_provider: str = "hashing"
    embedding_dim: int = 256

    image_provider: str = "placeholder"  # placeholder | external | openrouter
    external_image_enabled: bool = False
    external_image_url: str | None = None
    external_image_api_key: str | None = None

    storage_backend: str = "local"  # local | s3
    storage_dir: str = str(BACKEND_DIR / "data" / "files")
    s3_endpoint_url: str | None = None
    s3_bucket: str = "cartaad"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_region: str = "us-east-1"

    renderer: str = "pillow"  # playwright | pillow

    webhook_token: str | None = None  # /ingest/webhook (future WhatsApp/Telegram bot); disabled when empty


def single_analysis() -> bool:
    """Real providers analyze a capture in one vision call (analyze_capture) and generate with generate_content."""
    return get_settings().llm_provider == "openrouter"


@lru_cache
def get_settings() -> Settings:
    return Settings()
