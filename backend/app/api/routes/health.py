from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.database import check_database_connection
from app.core.settings import get_settings

router = APIRouter(tags=["System"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: str
    ai_mode: str
    camera_mode: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Check application health")
def health_check() -> HealthResponse:
    settings = get_settings()
    database_ok, database_status = check_database_connection()
    return HealthResponse(
        status="healthy" if database_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=database_status,
        ai_mode=settings.ai_mode,
        camera_mode=settings.camera_mode,
        timestamp=datetime.now(UTC),
    )
