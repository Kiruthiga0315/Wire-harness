from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Checkpoint, ProductModel
from app.schemas.inspection import MockInspectionRequest, MockInspectionResponse
from app.schemas.sticker import StickerFieldData, StickerInspectionReport
from app.services.active_image_service import active_image_service
from app.services.mock_inspection_service import MockInspectionService
from app.services.sticker_inspection_service import StickerInspectionService

router = APIRouter(prefix="/inspections", tags=["Inspections"])
logger = logging.getLogger(__name__)
mock_inspection_service = MockInspectionService()
sticker_service = StickerInspectionService()
DEMO_PROCESSING_SECONDS = 1.0


def _build_sticker_report() -> StickerInspectionReport:
    active = active_image_service.get_active_image()
    outcome = sticker_service.inspect(active.bgr_image)
    return StickerInspectionReport(
        present=outcome.present,
        status=outcome.status,
        notification=outcome.notification,
        confidence=outcome.confidence,
        fields=StickerFieldData(
            harness_code=outcome.fields.harness_code,
            part_number=outcome.fields.part_number,
            description=outcome.fields.description,
            drawing_number=outcome.fields.drawing_number,
            serial_number=outcome.fields.serial_number,
            barcode_payload=outcome.fields.barcode_payload,
            supplier=outcome.fields.supplier,
            batch_code=outcome.fields.batch_code,
        ),
        thumbnail=outcome.thumbnail_data_url,
    )


@router.get(
    "/sticker",
    response_model=StickerInspectionReport,
    summary="Inspect active image for specification sticker and extract details",
)
def get_active_sticker_inspection() -> StickerInspectionReport:
    try:
        return _build_sticker_report()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Sticker inspection failed: {exc}") from exc


@router.post(
    "/sticker",
    response_model=StickerInspectionReport,
    summary="Inspect active image for specification sticker and extract details",
)
def inspect_active_sticker() -> StickerInspectionReport:
    try:
        return _build_sticker_report()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Sticker inspection failed: {exc}") from exc


@router.post(
    "/demo/process",
    response_model=MockInspectionResponse,
    summary="Run deterministic mock inspection with sticker verification",
)
async def process_demo_inspection(
    payload: MockInspectionRequest,
    db: Session = Depends(get_db),
) -> MockInspectionResponse:
    model = db.scalar(select(ProductModel).where(ProductModel.model_id == payload.model_id))
    if model is None:
        raise HTTPException(status_code=404, detail="Product model not found")

    checkpoints = list(
        db.scalars(
            select(Checkpoint)
            .where(
                Checkpoint.model_id == payload.model_id,
                Checkpoint.enabled.is_(True),
                Checkpoint.checkpoint_id.like("CP-%"),
            )
            .order_by(Checkpoint.id)
        )
    )
    if not checkpoints:
        raise HTTPException(status_code=422, detail="No enabled checkpoints are configured")

    logger.info("Mock inspection started | model=%s", payload.model_id)
    await asyncio.sleep(DEMO_PROCESSING_SECONDS)
    try:
        active_rec = active_image_service.get_active_image()
        img_width = active_rec.width
        img_height = active_rec.height
        from app.api.routes.images import detect_table_box
        table_box = detect_table_box(active_rec.bgr_image)
    except Exception:
        img_width = None
        img_height = None
        table_box = None

    response = mock_inspection_service.evaluate(
        model,
        checkpoints,
        cycle_time_seconds=DEMO_PROCESSING_SECONDS,
        image_width=img_width,
        image_height=img_height,
        table_crop=table_box,
    )

    sticker_report = _build_sticker_report()
    # If sticker is not present, overall state becomes NG
    final_state = response.state if sticker_report.present else "NG"

    result_response = MockInspectionResponse(
        inspection_id=response.inspection_id,
        model_id=response.model_id,
        model_name=response.model_name,
        state=final_state,
        total_checkpoints=response.total_checkpoints,
        passed=response.passed,
        failed=response.failed if sticker_report.present else response.failed + 1,
        warnings=response.warnings,
        cycle_time_seconds=response.cycle_time_seconds,
        timestamp=response.timestamp,
        results=response.results,
        sticker_inspection=sticker_report,
    )

    logger.info(
        "Mock inspection completed | model=%s | result=%s | sticker=%s",
        payload.model_id,
        result_response.state,
        sticker_report.status,
    )
    return result_response
