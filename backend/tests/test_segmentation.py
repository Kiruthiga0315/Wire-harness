import asyncio

import cv2
import httpx
import numpy as np

from app.main import app
from app.services.harness_segmentation_service import HarnessSegmentationService


def test_segmentation_service_generates_requested_outputs() -> None:
    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    cv2.line(image, (45, 100), (155, 100), (0, 0, 0), 12)
    cv2.circle(image, (20, 20), 1, (0, 0, 0), -1)
    cv2.rectangle(image, (190, 0), (199, 199), (0, 0, 0), -1)

    result = HarnessSegmentationService(
        minimum_component_area_ratio=0.001,
        closing_kernel_size=5,
        closing_iterations=1,
    ).segment(image)

    assert result.binary_mask.shape == (200, 200)
    assert result.contour_image.shape == image.shape
    assert result.skeleton_image.shape == (200, 200)
    assert 0 < result.occupied_percentage < 10
    assert result.contour_count == 1
    assert result.removed_component_count >= 1
    assert result.excluded_border_component_count == 1
    assert cv2.countNonZero(result.skeleton_image) > 0


def test_demo_segmentation_api_returns_renderable_images() -> None:
    async def request_segmentation() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/engineering/segmentation/demo")

    response = asyncio.run(request_segmentation())

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_ready"] is False
    assert 0 < payload["metrics"]["harness_occupied_percentage"] < 100
    assert payload["metrics"]["contour_count"] > 0
    assert payload["images"]["binary_mask"].startswith("data:image/png;base64,")
    assert payload["images"]["contour_image"].startswith("data:image/png;base64,")
    assert payload["images"]["skeleton_image"].startswith("data:image/png;base64,")


def test_segmentation_service_preserves_edge_touching_workpiece() -> None:
    # Image where a major workpiece touches the left edge (x=0)
    # and spans across >30% width and >30% height, alongside a peripheral artifact on top edge.
    image = np.full((300, 300, 3), 255, dtype=np.uint8)

    # Main harness spanning across width and height, touching edge at x=0
    cv2.line(image, (0, 150), (200, 150), (0, 0, 0), 16)
    cv2.line(image, (200, 150), (200, 260), (0, 0, 0), 16)

    # Peripheral artifact: narrow strip on top border
    cv2.rectangle(image, (50, 0), (250, 2), (0, 0, 0), -1)

    result = HarnessSegmentationService().segment(image)

    # The spanning workpiece touching the edge must be preserved
    assert result.contour_count >= 1
    assert result.occupied_percentage > 2.0
    # The peripheral strip at the top border should be excluded
    assert result.excluded_border_component_count == 1
    assert cv2.countNonZero(result.skeleton_image) > 50

