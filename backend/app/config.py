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

    llm_provider: str = "mock"  # mock | anthropic
    llm_model: str | None = None
    anthropic_api_key: str | None = None
    llm_max_tokens: int = 4096

    embedding_provider: str = "hashing"
    embedding_dim: int = 256

    image_provider: str = "placeholder"  # placeholder | external
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
