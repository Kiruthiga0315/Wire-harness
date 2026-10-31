from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import cv2
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.services.active_image_service import active_image_service
from app.services.cloud_io import decode_uploaded_image
from app.services.golden_inspection_service import golden_inspection_service
from app.services.golden_reference_service import golden_reference_service

router = APIRouter(prefix="/golden-reference", tags=["Golden Reference"])


class CheckpointUpdateRequest(BaseModel):
    expected_value: float | None = None
    tolerance: float | None = None
    reference_x: int | None = None
    reference_y: int | None = None
    roi_width: int | None = None
    roi_height: int | None = None
    status: str | None = None
    notes: str | None = None
    terminal_id: str | None = None
    node_id: str | None = None
    branch_id: str | None = None
    measurement_type: str | None = None


class CheckpointCreateRequest(BaseModel):
    checkpoint_id: str
    type: str = "terminal"
    terminal_id: str | None = None
    node_id: str | None = None
    branch_id: str | None = None
    measurement_type: str = "branch_length"
    expected_value: float | None = None
    unit: str = "mm"
    tolerance: float | None = 15.0
    reference_x: int
    reference_y: int
    roi_width: int = 45
    roi_height: int = 45
    confidence: float = 0.95
    status: str = "CONFIRMED"
    notes: str = ""


class CalibrationUpdateRequest(BaseModel):
    known_distance_mm: float
    pixel_distance: float
    pixels_per_mm: float | None = None
    endpoint1: dict[str, int] | None = None
    endpoint2: dict[str, int] | None = None
    unit: str = "mm"
    method: str = "manual_calibration"


class InspectRequest(BaseModel):
    use_active_image: bool = True
    pixels_per_mm: float | None = None


@router.get("", summary="Get golden reference configuration and checkpoints")
def get_golden_reference() -> dict[str, Any]:
    return golden_reference_service.get_configuration()


@router.put("/checkpoints/{checkpoint_id}", summary="Update a single golden checkpoint")
def update_checkpoint(checkpoint_id: str, payload: CheckpointUpdateRequest) -> dict[str, Any]:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    try:
        return golden_reference_service.update_checkpoint(checkpoint_id, updates)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/checkpoints", summary="Add a new golden checkpoint")
def add_checkpoint(payload: CheckpointCreateRequest) -> dict[str, Any]:
    try:
        return golden_reference_service.add_checkpoint(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/checkpoints/{checkpoint_id}", summary="Delete a golden checkpoint")
def delete_checkpoint(checkpoint_id: str) -> dict[str, str]:
    try:
        golden_reference_service.delete_checkpoint(checkpoint_id)
        return {"message": f"Checkpoint '{checkpoint_id}' deleted successfully"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/checkpoints", summary="Clear all golden checkpoints")
@router.post("/clear-checkpoints", summary="Clear all golden checkpoints")
def clear_all_checkpoints() -> dict[str, Any]:
    return golden_reference_service.clear_all_checkpoints()


@router.post("/calibration", summary="Update measurement calibration")
def update_calibration(payload: CalibrationUpdateRequest) -> dict[str, Any]:
    data = payload.model_dump()
    if data["known_distance_mm"] <= 0:
        raise HTTPException(status_code=400, detail="known_distance_mm must be positive")
    if data.get("pixels_per_mm") is None or data["pixels_per_mm"] <= 0:
        data["pixels_per_mm"] = round(data["pixel_distance"] / data["known_distance_mm"], 4)
    data["calibrated"] = True
    return golden_reference_service.update_calibration(data)


@router.post("/sync-active-image", summary="Synchronize golden reference configuration and image with active test image")
def sync_golden_with_active_image() -> dict[str, Any]:
    try:
        return golden_reference_service.sync_with_active_image()
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to sync with active workpiece: {exc}") from exc


@router.post("/reset", summary="Reset golden reference to default baseline")
def reset_golden_reference() -> dict[str, Any]:
    return golden_reference_service.reset_to_baseline()


@router.get("/export/csv", summary="Export golden reference as CSV")
def export_csv() -> PlainTextResponse:
    csv_text = golden_reference_service.export_csv()
    return PlainTextResponse(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="golden_measurements.csv"'},
    )


@router.get("/export/json", summary="Export golden reference as JSON")
def export_json() -> dict[str, Any]:
    return golden_reference_service.get_configuration()


@router.get("/export/pdf", summary="Export golden reference inspection report as PDF")
def export_golden_pdf() -> Response:
    active = active_image_service.get_active_image()
    if active is None or active.bgr_image is None:
        raise HTTPException(status_code=400, detail="No active test image loaded.")

    from app.services.pdf_report_service import pdf_report_service
    from app.api.routes.reports import get_demo_report
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        report_response = get_demo_report(db)
        pdf_bytes = pdf_report_service.generate_pdf(report_response)
        filename = f"golden_inspection_{report_response.report_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


@router.get("/images/{image_name}", summary="Get golden reference image assets")
def get_golden_image(image_name: str) -> FileResponse:
    allowed = {
        "golden_harness.png": golden_reference_service.golden_image_path,
        "golden_harness.jpg": golden_reference_service.golden_image_path,
        "measurement_sheet.png": golden_reference_service.sheet_image_path,
        "golden_preview_annotated.png": golden_reference_service.data_dir / "golden_preview_annotated.png",
    }
    path = allowed.get(image_name)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=f"Image asset '{image_name}' not found")
    media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.post("/inspect", summary="Inspect active workpiece or uploaded image against Golden Reference")
def inspect_against_golden(payload: InspectRequest | None = None) -> dict[str, Any]:
    if payload is None:
        payload = InspectRequest()
    active = active_image_service.get_active_image()
    if active is None or active.bgr_image is None:
        raise HTTPException(status_code=400, detail="No active test image loaded. Upload an image first.")

    try:
        result = golden_inspection_service.inspect_image(
            active.bgr_image,
            override_pixels_per_mm=payload.pixels_per_mm,
        )
        return {
            "inspection_id": result.inspection_id,
            "timestamp": result.timestamp,
            "overall_status": result.overall_status,
            "total_checkpoints": result.total_checkpoints,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "review_count": result.review_count,
            "calibrated": result.calibrated,
            "pixels_per_mm": result.pixels_per_mm,
            "alignment_confidence": result.alignment_confidence,
            "marked_image_data_url": result.marked_image_data_url,
            "results": [
                {
                    "checkpoint_id": r.checkpoint_id,
                    "type": r.type,
                    "terminal_id": r.terminal_id,
                    "node_id": r.node_id,
                    "branch_id": r.branch_id,
                    "measurement_type": r.measurement_type,
                    "expected_value": r.expected_value,
                    "detected_value": r.detected_value,
                    "unit": r.unit,
                    "tolerance": r.tolerance,
                    "deviation": r.deviation,
                    "percentage_deviation": r.percentage_deviation,
                    "status": r.status,
                    "confidence": r.confidence,
                    "message": r.message,
                    "golden_coord": list(r.golden_coord),
                    "test_coord": list(r.test_coord),
                    "roi_bbox": list(r.roi_bbox),
                }
                for r in result.results
            ],
            "summary_notes": result.summary_notes,
            "topology_summary": result.topology_summary,
            "colored_tapes": result.colored_tapes,
            "sticker": result.sticker,
            "terminal_identifications": result.terminal_identifications,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Inspection failed: {exc}") from exc


@router.post("/inspect-upload", summary="Upload and inspect image against Golden Reference in one step")
async def inspect_uploaded_image(file: UploadFile = File(...)) -> dict[str, Any]:
    contents = await file.read()
    try:
        bgr_image = decode_uploaded_image(contents, filename=file.filename or "upload.png", content_type=file.content_type)
        result = golden_inspection_service.inspect_image(bgr_image)
        return {
            "inspection_id": result.inspection_id,
            "timestamp": result.timestamp,
            "overall_status": result.overall_status,
            "total_checkpoints": result.total_checkpoints,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "review_count": result.review_count,
            "calibrated": result.calibrated,
            "pixels_per_mm": result.pixels_per_mm,
            "alignment_confidence": result.alignment_confidence,
            "marked_image_data_url": result.marked_image_data_url,
            "results": [
                {
                    "checkpoint_id": r.checkpoint_id,
                    "type": r.type,
                    "terminal_id": r.terminal_id,
                    "node_id": r.node_id,
                    "branch_id": r.branch_id,
                    "measurement_type": r.measurement_type,
                    "expected_value": r.expected_value,
                    "detected_value": r.detected_value,
                    "unit": r.unit,
                    "tolerance": r.tolerance,
                    "deviation": r.deviation,
                    "percentage_deviation": r.percentage_deviation,
                    "status": r.status,
                    "confidence": r.confidence,
                    "message": r.message,
                    "golden_coord": list(r.golden_coord),
                    "test_coord": list(r.test_coord),
                    "roi_bbox": list(r.roi_bbox),
                }
                for r in result.results
            ],
            "summary_notes": result.summary_notes,
            "topology_summary": result.topology_summary,
            "colored_tapes": result.colored_tapes,
            "sticker": result.sticker,
            "terminal_identifications": result.terminal_identifications,
        }
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Inspection failed: {exc}") from exc
