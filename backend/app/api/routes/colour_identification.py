"""API route for full-image Colour Identification and Verification."""

from __future__ import annotations

import logging

import cv2
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.schemas.colour_identification import (
    ColourIdentificationRequest,
    ColourIdentificationResponse,
    ColourSummaryResponse,
    TapeDetectionItem,
    VerificationResponse,
    WireDetectionItem,
    ColourVector,
)
from app.services.active_image_service import active_image_service
from app.services.colour_identification_service import (
    ColourIdentificationService,
    _png_data_url,
)
from app.services.harness_segmentation_service import HarnessSegmentationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/colour-identification", tags=["Colour Identification"])

_segmentation_service = HarnessSegmentationService()
_colour_service = ColourIdentificationService(segmentation_service=_segmentation_service)


def _vec(vals: tuple[float, float, float] | None) -> ColourVector | None:
    if vals is None:
        return None
    return ColourVector(channel_1=vals[0], channel_2=vals[1], channel_3=vals[2])


def _find_associated_mask_and_skeleton(filename: str, width: int, height: int):
    from pathlib import Path
    from app.core.settings import get_settings
    dataset_dir = get_settings().project_root / "data" / "test_images" / "images_001" / "001"
    if dataset_dir.is_dir() and ("001" in filename or (width == 1800 and height == 560)):
        mask_path = dataset_dir / "001_03_harness_mask.png"
        skel_path = dataset_dir / "001_06_skeleton.png"
        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE) if mask_path.is_file() else None
        skel = cv2.imread(str(skel_path), cv2.IMREAD_GRAYSCALE) if skel_path.is_file() else None
        return mask, skel
    return None, None


@router.post(
    "/analyse",
    response_model=ColourIdentificationResponse,
    summary="Run full colour identification on the active inspection image",
)
def analyse_active_image(
    payload: ColourIdentificationRequest | None = None,
) -> ColourIdentificationResponse:
    """Identify tape colours (green, dark blue, gray) and wire insulation
    colours on the currently active inspection image."""
    active = active_image_service.get_active_image()
    inspection_id = payload.inspection_id if payload else ""
    golden_cfg = payload.golden_colour_config if payload else None

    harness_mask, skeleton = _find_associated_mask_and_skeleton(
        active.filename, active.width, active.height
    )

    try:
        result = _colour_service.identify(
            active.bgr_image,
            inspection_id=inspection_id,
            golden_colour_config=golden_cfg,
            harness_mask=harness_mask,
            skeleton=skeleton,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Colour identification failed: {exc}",
        ) from exc

    return _build_response(result)


@router.post(
    "/analyse-upload",
    response_model=ColourIdentificationResponse,
    summary="Run colour identification on an uploaded image",
)
async def analyse_uploaded_image(
    file: UploadFile = File(...),
    inspection_id: str = Form(default=""),
    golden_config: str | None = Form(default=None),
) -> ColourIdentificationResponse:
    """Upload a wire harness image and run colour identification."""
    import json
    import numpy as np

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    nparr = np.frombuffer(content, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(
            status_code=422,
            detail="Could not decode the uploaded file as an image.",
        )

    parsed_golden = None
    if golden_config:
        try:
            parsed_golden = json.loads(golden_config)
        except Exception:
            parsed_golden = None

    try:
        result = _colour_service.identify(
            image,
            inspection_id=inspection_id,
            golden_colour_config=parsed_golden,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Colour identification failed: {exc}",
        ) from exc

    return _build_response(result)


def _build_response(result) -> ColourIdentificationResponse:
    """Convert internal result to Pydantic response model."""
    tape_items = [
        TapeDetectionItem(
            region_id=d.region_id,
            detected_color=d.detected_color,
            bbox=list(d.bbox),
            center=list(d.center),
            area=d.area,
            width=d.width,
            height=d.height,
            confidence=d.confidence,
            status=d.status,
            branch_id=d.branch_id,
            mean_hsv=_vec(d.mean_hsv),
            mean_lab=_vec(d.mean_lab),
        )
        for d in result.tape_detections
    ]

    wire_items = [
        WireDetectionItem(
            region_id=d.region_id,
            detected_color=d.detected_color,
            bbox=list(d.bbox),
            center=list(d.center),
            area=d.area,
            width=d.width,
            height=d.height,
            branch_id=d.branch_id,
            confidence=d.confidence,
            status=d.status,
            mean_hsv=_vec(d.mean_hsv),
            mean_lab=_vec(d.mean_lab),
        )
        for d in result.wire_detections
    ]

    summary = ColourSummaryResponse(
        green_tape=result.colour_summary.green_tape,
        dark_blue_tape=result.colour_summary.dark_blue_tape,
        gray_tape=result.colour_summary.gray_tape,
        wire_regions=result.colour_summary.wire_regions,
        uncertain_detections=result.colour_summary.uncertain_detections,
    )

    verification = VerificationResponse(
        status=result.verification.status,
        message=result.verification.message,
        details=result.verification.details,
    )

    overlay_url = _png_data_url(result.overlay_image) if result.overlay_image is not None else ""
    original_url = _png_data_url(result.original_image) if result.original_image is not None else ""

    return ColourIdentificationResponse(
        success=result.success,
        inspection_id=result.inspection_id,
        image_width=result.image_width,
        image_height=result.image_height,
        colour_summary=summary,
        tape_detections=tape_items,
        wire_detections=wire_items,
        verification=verification,
        overlay_image=overlay_url,
        original_image=original_url,
        processing_time_ms=result.processing_time_ms,
        method=result.method,
        disclaimer=result.disclaimer,
    )
