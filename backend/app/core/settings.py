from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


load_dotenv(_project_root() / ".env")


def _database_url() -> str:
    configured = os.getenv("DATABASE_URL")
    if not configured:
        return f"sqlite:///{(_project_root() / 'data' / 'inspection.db').as_posix()}"
    if not configured.startswith("sqlite:///"):
        return configured

    sqlite_path = configured.removeprefix("sqlite:///")
    if sqlite_path == ":memory:":
        return configured
    path = Path(sqlite_path)
    if not path.is_absolute():
        path = (_project_root() / path).resolve()
    return f"sqlite:///{path.as_posix()}"


def _storage_path(environment_key: str, default_relative_path: str) -> str:
    path = Path(os.getenv(environment_key, default_relative_path))
    if not path.is_absolute():
        path = (_project_root() / path).resolve()
    return str(path)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "AI Wire Harness Final Inspection System")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    environment: str = os.getenv("ENVIRONMENT", "development")
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    frontend_url: str = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
    database_url: str = _database_url()
    image_storage_path: str = _storage_path("IMAGE_STORAGE_PATH", "data/captured_images")
    model_storage_path: str = _storage_path("MODEL_STORAGE_PATH", "data/models")
    ai_mode: str = os.getenv("AI_MODE", "mock")
    camera_mode: str = os.getenv("CAMERA_MODE", "mock")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def project_root(self) -> Path:
        return _project_root()

    def ensure_directories(self) -> None:
        for path in (
            Path(self.image_storage_path),
            Path(self.model_storage_path),
            self.project_root / "data" / "inspection_results",
            self.project_root / "data" / "calibration",
            self.project_root / "data" / "reference_images",
            self.project_root / "data" / "reports",
            self.project_root / "logs",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
