from __future__ import annotations

import csv
import io
import json

import cv2
import numpy as np
import pytest

from app.services.cloud_io import (
    UploadedImageValidationError,
    decode_uploaded_image,
    encode_annotated_png,
    inspection_csv_bytes,
    inspection_json_bytes,
)
from app.services.inspection_engine import InspectionEngine


def _image_bytes(extension: str = ".png", *, width: int = 160, height: int = 120) -> bytes:
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    cv2.line(image, (15, height // 2), (width - 15, height // 2), (20, 20, 20), 8)
    cv2.line(image, (width // 2, height // 2), (width // 2, height - 15), (20, 20, 20), 8)
    ok, encoded = cv2.imencode(extension, image)
    assert ok
    return encoded.tobytes()


@pytest.mark.parametrize(
    ("extension", "content_type"),
    [
        (".png", "image/png"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
        (".bmp", "image/bmp"),
        (".bmp", "image/x-ms-bmp"),
    ],
)
def test_valid_upload_decodes_to_bgr(extension: str, content_type: str) -> None:
    decoded = decode_uploaded_image(
        _image_bytes(extension),
        filename=f"harness{extension}",
        content_type=content_type,
    )
    assert decoded.shape == (120, 160, 3)
    assert decoded.dtype == np.uint8


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(UploadedImageValidationError, match="Only JPG, JPEG, PNG, and BMP"):
        decode_uploaded_image(
            _image_bytes(), filename="harness.gif", content_type="image/gif"
        )


def test_mismatched_or_corrupt_upload_is_rejected() -> None:
    with pytest.raises(UploadedImageValidationError, match="extension does not match"):
        decode_uploaded_image(
            _image_bytes(".png"), filename="harness.jpg", content_type="image/jpeg"
        )
    with pytest.raises(UploadedImageValidationError, match="extension does not match"):
        decode_uploaded_image(
            _image_bytes(".png"), filename="harness.bmp", content_type="image/bmp"
        )
    with pytest.raises(UploadedImageValidationError, match="corrupted"):
        decode_uploaded_image(
            b"not an image", filename="harness.bmp", content_type="image/bmp"
        )


def test_upload_bounds_are_enforced() -> None:
    payload = _image_bytes(width=80, height=80)
    with pytest.raises(UploadedImageValidationError, match="exceeds"):
        decode_uploaded_image(
            payload,
            filename="harness.png",
            content_type="image/png",
            max_bytes=10,
        )
    with pytest.raises(UploadedImageValidationError, match="dimensions exceed"):
        decode_uploaded_image(
            payload,
            filename="harness.png",
            content_type="image/png",
            max_dimension=64,
        )


def test_png_json_and_csv_downloads_are_valid(tmp_path) -> None:
    image = decode_uploaded_image(
        _image_bytes(), filename="harness.png", content_type="image/png"
    )
    result = InspectionEngine(project_root=tmp_path).inspect_harness(image)

    png = encode_annotated_png(result)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")

    summary = json.loads(inspection_json_bytes(result))
    assert summary["inspection_id"] == result.inspection_id
    assert summary["overall_status"] == "NOT_EVALUATED"

    rows = list(csv.DictReader(io.StringIO(inspection_csv_bytes(result).decode("utf-8-sig"))))
    assert rows[0]["record_type"] == "INSPECTION"
    assert {row["record_type"] for row in rows} >= {"INSPECTION", "RULE", "MEASUREMENT"}


def test_bmp_image_processing_in_inspection_engine(tmp_path) -> None:
    bmp_payload = _image_bytes(".bmp", width=120, height=90)
    image = decode_uploaded_image(
        bmp_payload, filename="harness_test.bmp", content_type="image/bmp"
    )
    assert image.shape == (90, 120, 3)
    result = InspectionEngine(project_root=tmp_path).inspect_harness(image)
    assert result.image_width == 120
    assert result.image_height == 90
    assert result.annotated_image.shape == (90, 120, 3)
