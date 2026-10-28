from fastapi import APIRouter

from app.api.routes import checkpoints, engineering, golden_reference, health, images, inspections, reports

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(images.router)
api_router.include_router(engineering.router)
api_router.include_router(checkpoints.router)
api_router.include_router(golden_reference.router)
api_router.include_router(inspections.router)
api_router.include_router(reports.router)
