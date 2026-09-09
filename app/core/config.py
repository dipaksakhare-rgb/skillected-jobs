"""Application configuration (§103: environment variables, strong typing)."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    """Central typed settings loaded from environment/.env."""

    def __init__(self) -> None:
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.app_base_url: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
        self.app_secret: str = os.getenv("APP_SECRET", "dev-only-secret-change-me")
        self.db_engine: str = os.getenv("DB_ENGINE", "sqlite")
        self.database_url: str = os.getenv("DATABASE_URL", "sqlite:///data/skillected.db")
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")

        # Provider seams (§106): swap implementations without app rewrites.
        self.ai_provider: str = os.getenv("AI_PROVIDER", "none")
        self.queue_backend: str = os.getenv("QUEUE_BACKEND", "inline")
        self.storage_backend: str = os.getenv("STORAGE_BACKEND", "local")
        self.whatsapp_provider: str = os.getenv("WHATSAPP_PROVIDER", "none")
        self.analytics_provider: str = os.getenv("ANALYTICS_PROVIDER", "internal")

        self.admin_email: str = os.getenv("ADMIN_EMAIL", "admin@skillected.local")
        self.admin_password: str = os.getenv("ADMIN_PASSWORD", "ChangeMe!Admin1")

        self.session_cookie: str = "skillected_session"
        self.session_ttl_hours_user: int = 24 * 7
        self.session_ttl_hours_admin: int = 8
        self.data_dir: Path = PROJECT_ROOT / "data"
        self.static_dir: Path = PROJECT_ROOT / "app" / "static"
        self.templates_dir: Path = PROJECT_ROOT / "app" / "templates"

    @property
    def sqlite_path(self) -> Path:
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix):]
            path = Path(raw if os.path.isabs(raw) else PROJECT_ROOT / raw)
        else:
            path = self.data_dir / "skillected.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_prod(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
