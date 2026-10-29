from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np
import pytest

from app.services.wire_color_service import WireColorIdentificationService


def _create_synthetic_4_wire_board() -> np.ndarray:
    """Create a test image with light board and four distinct wire conductors."""
    img = np.full((360, 400, 3), 240, dtype=np.uint8)
    # 1. Dark Blue wire: BGR (85, 45, 20) -> Distinct blue dominance
    cv2.line(img, (40, 50), (360, 50), (85, 45, 20), 8)
    # 2. Grey wire: BGR (115, 115, 115) -> Neutral mid-luminance
    cv2.line(img, (40, 130), (360, 130), (115, 115, 115), 8)
    # 3. Black wire: BGR (28, 28, 28) -> Neutral dark
    cv2.line(img, (40, 210), (360, 210), (28, 28, 28), 8)
    # 4. Green wire: BGR (30, 95, 30) -> Distinct green dominance
    cv2.line(img, (40, 290), (360, 290), (30, 95, 30), 8)
    return img


def test_synthetic_wires_all_four_detected() -> None:
    img = _create_synthetic_4_wire_board()
    service = WireColorIdentificationService(
        min_pixels_dark_blue=30,
        min_pixels_grey=30,
        min_pixels_green=30,
        min_pixels_black=30,
    )
    res = service.identify_colors(img, "synthetic_4_wires.png")

    assert res.analyzed_wire_pixels > 0
    assert len(res.colors) == 4

    colors = {c.color_id: c for c in res.colors}
    assert colors["dark_blue"].detected is True
    assert colors["dark_blue"].status == "Detected"
    assert colors["dark_blue"].confidence >= 0.70

    assert colors["grey"].detected is True
    assert colors["grey"].status == "Detected"
    assert colors["grey"].confidence >= 0.70

    assert colors["black"].detected is True
    assert colors["black"].status == "Detected"
    assert colors["black"].confidence >= 0.70

    assert colors["green"].detected is True
    assert colors["green"].status == "Detected"
    assert colors["green"].confidence >= 0.70

    assert res.overlay_image.startswith("data:image/png;base64,")
    assert res.original_image.startswith("data:image/png;base64,")
    assert len(res.sections) > 0

    # Ensure sections include original_crop and bounding boxes
    for sec in res.sections:
        assert sec.cropped_image.startswith("data:image/png;base64,")
        assert sec.original_crop is not None
        assert sec.original_crop.startswith("data:image/png;base64,")
        assert sec.width > 0
        assert sec.height > 0


def test_missing_color_truthfully_reports_not_detected() -> None:
    # Image with only dark blue, grey, and black wires (no green wire)
    img = np.full((300, 400, 3), 240, dtype=np.uint8)
    cv2.line(img, (40, 60), (360, 60), (85, 45, 20), 8)
    cv2.line(img, (40, 140), (360, 140), (115, 115, 115), 8)
    cv2.line(img, (40, 220), (360, 220), (28, 28, 28), 8)

    service = WireColorIdentificationService(
        min_pixels_dark_blue=30,
        min_pixels_grey=30,
        min_pixels_green=30,
        min_pixels_black=30,
    )
    res = service.identify_colors(img, "three_wires.png")

    colors = {c.color_id: c for c in res.colors}
    assert colors["dark_blue"].detected is True
    assert colors["grey"].detected is True
    assert colors["black"].detected is True
    assert colors["green"].detected is False
    assert colors["green"].status == "Not detected"
    assert colors["green"].confidence == 0.0


def test_thick_tape_and_specular_glare_are_excluded() -> None:
    img = np.full((300, 400, 3), 240, dtype=np.uint8)
    # Thin wire (width 8)
    cv2.line(img, (40, 100), (360, 100), (28, 28, 28), 8)
    # Thick 60x60 black block simulating connector body or heavy tape wrapping
    cv2.rectangle(img, (140, 70), (260, 130), (28, 28, 28), -1)
    # Specular white reflection inside the block
    cv2.circle(img, (200, 100), 10, (245, 245, 245), -1)

    service = WireColorIdentificationService()
    res = service.identify_colors(img, "tape_exclusion.png")

    # Wire candidate area should exclude the thick center of the 60x60 block
    assert res.analyzed_wire_pixels < res.total_harness_pixels


def test_real_reference_harness_identification() -> None:
    ref_path = Path("data/reference_images/ref_harness_vertical_2.jpg")
    if not ref_path.is_file():
        pytest.skip("Reference image ref_harness_vertical_2.jpg not present")

    img = cv2.imread(str(ref_path))
    assert img is not None

    service = WireColorIdentificationService()
    res = service.identify_colors(img, "ref_harness_vertical_2.jpg")

    assert res.total_harness_pixels > 10000
    assert len(res.colors) == 4

    colors = {c.color_id: c for c in res.colors}
    assert colors["dark_blue"].status in ("Detected", "Uncertain")
    assert colors["grey"].status in ("Detected", "Uncertain")
    assert colors["black"].status in ("Detected", "Uncertain")
    assert colors["green"].status in ("Detected", "Uncertain", "Not detected")

    assert len(res.sections) > 0
    # Check that sections are non-overlapping
    for i, s1 in enumerate(res.sections):
        for j, s2 in enumerate(res.sections):
            if i != j:
                # Assert no center point collision
                dist = np.hypot((s1.x + s1.width / 2) - (s2.x + s2.width / 2), (s1.y + s1.height / 2) - (s2.y + s2.height / 2))
                assert dist >= 15
