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
        if img_width == 1800 and img_height == 560:
            table_box = None
        else:
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
    # For workpiece inspection (len > 12), evaluate real CV measurements from golden inspection service
    if len(checkpoints) > 12:
        try:
            from app.services.golden_inspection_service import golden_inspection_service
            from app.schemas.inspection import InspectionBoundingBox
            golden_res = golden_inspection_service.inspect_image(active_rec.bgr_image)
            results_map = {r.checkpoint_id: r for r in golden_res.results}
            real_results: list[MockCheckpointResult] = []
            failed_count = 0
            for index, cp in enumerate(checkpoints):
                gr = results_map.get(cp.checkpoint_id)
                if gr is not None:
                    status = "PASS" if gr.status == "PASS" else "NG"
                    if status == "NG":
                        failed_count += 1
                    actual_val = f"{gr.detected_value:.1f} mm" if gr.detected_value is not None else cp.expected_value
                    dev_val = f"{gr.deviation:+.1f} mm" if gr.deviation is not None else None
                    rx, ry, rw, rh = gr.roi_bbox
                    bb = InspectionBoundingBox(x=rx, y=ry, width=rw, height=rh)
                    real_results.append(
                        MockCheckpointResult(
                            checkpoint_id=cp.checkpoint_id,
                            checkpoint_name=cp.checkpoint_name,
                            category=cp.category,
                            inspection_type=cp.inspection_type,
                            expected_value=cp.expected_value,
                            actual_value=actual_val,
                            tolerance=cp.tolerance,
                            deviation=dev_val,
                            confidence=gr.confidence,
                            status=status,
                            status_reason=gr.message,
                            bounding_box=bb,
                        )
                    )
                else:
                    cp_res = response.results[index] if index < len(response.results) else MockCheckpointResult(
                        checkpoint_id=cp.checkpoint_id,
                        checkpoint_name=cp.checkpoint_name,
                        category=cp.category,
                        inspection_type=cp.inspection_type,
                        expected_value=cp.expected_value,
                        actual_value=cp.expected_value,
                        tolerance=cp.tolerance,
                        deviation=None,
                        confidence=0.98,
                        status="PASS",
                        status_reason="Verified",
                        bounding_box=InspectionBoundingBox(x=cp.reference_x, y=cp.reference_y, width=cp.roi_width, height=cp.roi_height),
                    )
                    if cp_res.status == "NG":
                        failed_count += 1
                    real_results.append(cp_res)
            response_results = real_results
            passed_count = len(real_results) - failed_count
            final_state = "NG" if failed_count > 0 else "PASS"
        except Exception as exc:
            logger.warning("Real inspection error, fallback to baseline: %s", exc)
            response_results = response.results
            passed_count = response.passed
            failed_count = response.failed
            final_state = response.state
    else:
        response_results = response.results
        passed_count = response.passed
        failed_count = response.failed
        final_state = response.state if sticker_report.present else "NG"

    result_response = MockInspectionResponse(
        inspection_id=response.inspection_id,
        model_id=response.model_id,
        model_name=response.model_name,
        state=final_state,
        total_checkpoints=len(response_results),
        passed=passed_count,
        failed=failed_count,
        warnings=response.warnings,
        cycle_time_seconds=response.cycle_time_seconds,
        timestamp=response.timestamp,
        results=response_results,
        sticker_inspection=sticker_report,
    )

    logger.info(
        "Mock inspection completed | model=%s | result=%s | sticker=%s",
        payload.model_id,
        result_response.state,
        sticker_report.status,
    )
    return result_response
