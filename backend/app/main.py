from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.database import check_database_connection, initialize_database
from app.core.logging_config import configure_logging
from app.core.settings import get_settings

settings = get_settings()
settings.ensure_directories()
configure_logging(settings.project_root / "logs", settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Application startup | environment=%s", settings.environment)
    database_ok, database_status = check_database_connection()
    if database_ok:
        initialize_database()
        logger.info("Database connection ready | %s", database_status)
    else:
        logger.error("Database unavailable | %s", database_status)
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-oriented API foundation for automotive wire harness inspection.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "status": "online",
        "documentation": "/docs",
    }
