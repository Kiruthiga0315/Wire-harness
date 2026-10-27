from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse

from app.core.settings import get_settings

router = APIRouter(prefix="/test-images", tags=["Test Images"])

DEMO_IMAGE_LOGICAL_NAME = "harness_sample_01.jpeg"
DEMO_IMAGE_CANDIDATES = (
    DEMO_IMAGE_LOGICAL_NAME,
    f"{DEMO_IMAGE_LOGICAL_NAME}.jpeg",
)


def resolve_demo_image() -> Path | None:
    test_image_directory = get_settings().project_root / "data" / "test_images"
    for filename in DEMO_IMAGE_CANDIDATES:
        candidate = test_image_directory / filename
        if candidate.is_file():
            return candidate
    return None


@router.post(
    "/active",
    summary="Upload and set the active inspection image across operations",
)
async def upload_active_image(file: UploadFile = File(...)) -> dict[str, object]:
    from app.services.active_image_service import active_image_service
    from app.services.cloud_io import UploadedImageValidationError

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


@router.get(
    "/active",
    summary="Retrieve the current active inspection image",
)
def get_active_image() -> Response:
    from app.services.active_image_service import active_image_service

    try:
        record = active_image_service.get_active_image()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        content=record.data,
        media_type=record.content_type,
        headers={
            "Cache-Control": "no-store",
            "X-Image-Source": record.source,
            "X-Image-Filename": record.filename,
        },
    )


@router.get(
    "/active/metadata",
    summary="Retrieve metadata of the current active inspection image",
)
def get_active_image_metadata() -> dict[str, object]:
    from app.services.active_image_service import active_image_service

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
    from app.services.active_image_service import active_image_service

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
