from pathlib import Path

from fastapi import APIRouter, HTTPException
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
