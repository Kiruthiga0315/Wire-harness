from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.services.active_image_service import (
    DEMO_IMAGE_CANDIDATES,
    DEMO_IMAGE_LOGICAL_NAME,
    active_image_service,
    resolve_demo_image,
)
from app.services.cloud_io import UploadedImageValidationError

router = APIRouter(prefix="/test-images", tags=["Test Images"])


@router.post(
    "/active",
    summary="Upload and set the active inspection image across operations",
)
async def upload_active_image(file: UploadFile = File(...)) -> dict[str, object]:
    payload = await file.read()
    try:
        record = active_image_service.set_uploaded_image(
            payload,
            filename=file.filename or "uploaded_image.png",
            content_type=file.content_type,
        )
    except UploadedImageValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image upload failed: {exc}") from exc

    return {
        "status": "success",
        "filename": record.filename,
        "content_type": record.content_type,
        "width": record.width,
        "height": record.height,
        "size": len(record.data),
        "source": record.source,
    }


def detect_table_box(bgr_image: np.ndarray) -> tuple[int, int, int, int] | None:
    height, width = bgr_image.shape[:2]
    if width <= 1000:
        return None
    grayscale = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)
    _, bright = cv2.threshold(blurred, 205, 255, cv2.THRESH_BINARY)
    kernel_table = cv2.getStructuringElement(cv2.MORPH_RECT, (35, 35))
    table_closed = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel_table)
    cnts, _ = cv2.findContours(table_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_area = 0.0
    table_box = None
    for c in cnts:
        area = float(cv2.contourArea(c))
        if area > (height * width * 0.05):
            bx, by, bw, bh = cv2.boundingRect(c)
            if area > max_area:
                max_area = area
                table_box = (bx, by, bw, bh)
    if table_box is not None:
        tx, ty, tw, th = table_box
        pad_x, pad_y = int(tw * 0.02), int(th * 0.02)
        tx1 = max(0, tx + pad_x)
        ty1 = max(0, ty + pad_y)
        tx2 = min(width, tx + tw - pad_x)
        ty2 = min(height, ty + th - pad_y)
        return (tx1, ty1, tx2 - tx1, ty2 - ty1)
    return None


@router.get(
    "/active/cropped",
    summary="Retrieve the cropped table view of the current active inspection image",
)
def get_active_image_cropped() -> Response:
    try:
        record = active_image_service.get_active_image()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    table_box = detect_table_box(record.bgr_image)
    if table_box is None:
        return Response(
            content=record.data,
            media_type=record.content_type,
            headers={
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
                "X-Is-Cropped": "false",
            },
        )

    tx, ty, tw, th = table_box
    cropped_bgr = record.bgr_image[ty:ty + th, tx:tx + tw]
    success, encoded = cv2.imencode(".jpg", cropped_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode cropped table image")

    return Response(
        content=encoded.tobytes(),
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "X-Is-Cropped": "true",
            "X-Crop-X": str(tx),
            "X-Crop-Y": str(ty),
            "X-Crop-Width": str(tw),
            "X-Crop-Height": str(th),
            "X-Original-Width": str(record.width),
            "X-Original-Height": str(record.height),
        },
    )


@router.get(
    "/active",
    summary="Retrieve the current active inspection image",
)
@router.head(
    "/active",
    summary="Check status and headers of current active inspection image",
)
def get_active_image() -> Response:
    try:
        record = active_image_service.get_active_image()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=record.data,
        media_type=record.content_type,
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "X-Image-Source": record.source,
            "X-Image-Filename": record.filename.encode("ascii", "replace").decode("ascii"),
        },
    )


@router.get(
    "/active/metadata",
    summary="Retrieve metadata of the current active inspection image",
)
def get_active_image_metadata() -> dict[str, object]:
    try:
        record = active_image_service.get_active_image()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "filename": record.filename,
        "content_type": record.content_type,
        "width": record.width,
        "height": record.height,
        "size": len(record.data),
        "source": record.source,
    }


@router.delete(
    "/active",
    summary="Reset active inspection image back to the demo image",
)
def reset_active_image() -> dict[str, object]:
    record = active_image_service.reset_to_demo()
    return {
        "status": "reset",
        "filename": record.filename,
        "source": record.source,
        "width": record.width,
        "height": record.height,
    }


@router.get(
    f"/{DEMO_IMAGE_LOGICAL_NAME}",
    response_class=FileResponse,
    summary="Load the development harness test image",
)
def get_demo_image() -> FileResponse:
    image_path = resolve_demo_image()
    if image_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"Demo image is missing from data/test_images/{DEMO_IMAGE_LOGICAL_NAME}",
        )

    return FileResponse(
        path=image_path,
        media_type="image/jpeg",
        filename=DEMO_IMAGE_LOGICAL_NAME,
        headers={
            "Cache-Control": "no-store",
            "X-Image-Source": f"data/test_images/{DEMO_IMAGE_LOGICAL_NAME}",
        },
    )
