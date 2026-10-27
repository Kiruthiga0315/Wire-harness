from __future__ import annotations

import io
import cv2
import numpy as np
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


def _create_test_image(extension: str = ".png", width: int = 120, height: int = 90) -> bytes:
    image = np.full((height, width, 3), 240, dtype=np.uint8)
    cv2.line(image, (10, height // 2), (width - 10, height // 2), (20, 20, 20), 6)
    cv2.line(image, (width // 2, 10), (width // 2, height - 10), (20, 20, 20), 6)
    ok, encoded = cv2.imencode(extension, image)
    assert ok
    return encoded.tobytes()


@pytest.mark.asyncio
async def test_active_image_lifecycle() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default should be demo image
        meta_res = await client.get("/api/test-images/active/metadata")
        assert meta_res.status_code == 200
        meta = meta_res.json()
        assert meta["source"] == "demo"
        assert meta["filename"] == "harness_sample_01.jpeg"

        # Active image download
        active_res = await client.get("/api/test-images/active")
        assert active_res.status_code == 200
        assert active_res.headers.get("x-image-source") == "demo"

        # Upload a custom PNG image
        custom_png = _create_test_image(".png", width=140, height=100)
        upload_res = await client.post(
            "/api/test-images/active",
            files={"file": ("custom_harness.png", io.BytesIO(custom_png), "image/png")},
        )
        assert upload_res.status_code == 200
        upload_meta = upload_res.json()
        assert upload_meta["source"] == "upload"
        assert upload_meta["filename"] == "custom_harness.png"
        assert upload_meta["width"] == 140
        assert upload_meta["height"] == 100

        # Verify active metadata reflects custom image
        meta_res2 = await client.get("/api/test-images/active/metadata")
        assert meta_res2.status_code == 200
        assert meta_res2.json()["source"] == "upload"
        assert meta_res2.json()["width"] == 140

        # Verify engineering segmentation reflects custom image
        seg_res = await client.post("/api/engineering/segmentation/demo")
        assert seg_res.status_code == 200
        seg_data = seg_res.json()
        assert seg_data["source_image"] == "custom_harness.png"
        assert seg_data["metrics"]["image_width"] == 140
        assert seg_data["metrics"]["image_height"] == 100

        # Upload a custom BMP image
        custom_bmp = _create_test_image(".bmp", width=160, height=110)
        upload_bmp_res = await client.post(
            "/api/test-images/active",
            files={"file": ("custom_sample.bmp", io.BytesIO(custom_bmp), "image/bmp")},
        )
        assert upload_bmp_res.status_code == 200
        assert upload_bmp_res.json()["filename"] == "custom_sample.bmp"
        assert upload_bmp_res.json()["width"] == 160
        assert upload_bmp_res.json()["height"] == 110

        # Reset back to demo
        del_res = await client.delete("/api/test-images/active")
        assert del_res.status_code == 200
        assert del_res.json()["source"] == "demo"

        # Verify reset back to demo in metadata
        meta_res3 = await client.get("/api/test-images/active/metadata")
        assert meta_res3.json()["source"] == "demo"
