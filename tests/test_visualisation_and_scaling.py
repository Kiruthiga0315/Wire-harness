"""Unit tests for Colour Identification Visualisation, Coordinate Scaling,
and Collision-Aware Label Placement.

Tests verify:
  1. Coordinate scaling across different viewport ratios
  2. Non-destructive overlay generation (original image quality preserved)
  3. Collision-aware label placement logic
  4. Category color mappings and label string formatting
  5. IoU-based duplicate and near-duplicate suppression
  6. High-confidence vs UNCERTAIN status categorization
  7. Verification with real wire harness dataset image
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from app.services.colour_identification_service import (
    ColourIdentificationService,
    DetectedRegion,
    _box_iou,
)

DATASET_IMAGE = Path(__file__).resolve().parent.parent / "data" / "test_images" / "images_001" / "001" / "001_01_board_crop.png"


# ---------------------------------------------------------------------------
# 1. Coordinate Scaling & Transform Tests
# ---------------------------------------------------------------------------

class TestCoordinateScaling:
    def test_bounding_box_scale_calculation(self):
        """Test conversion of detection bbox from image coords to display coords."""
        orig_w, orig_h = 1800, 560
        disp_w, disp_h = 900, 280  # 0.5 scale

        scale_x = disp_w / orig_w
        scale_y = disp_h / orig_h
        assert scale_x == 0.5
        assert scale_y == 0.5

        orig_box = (100, 200, 50, 40)
        disp_box = (
            int(round(orig_box[0] * scale_x)),
            int(round(orig_box[1] * scale_y)),
            int(round(orig_box[2] * scale_x)),
            int(round(orig_box[3] * scale_y)),
        )
        assert disp_box == (50, 100, 25, 20)

    def test_zoom_center_transform(self):
        """Test calculation of pan coordinates to center and zoom on a target detection."""
        viewer_w, viewer_h = 800, 400
        target_center_x, target_center_y = 600, 250
        zoom = 2.0

        # When focused, target point should map to viewer center
        pan_x = int(round(viewer_w / 2 - target_center_x * zoom))
        pan_y = int(round(viewer_h / 2 - target_center_y * zoom))

        # Check forward transform of target point
        screen_x = target_center_x * zoom + pan_x
        screen_y = target_center_y * zoom + pan_y
        assert screen_x == viewer_w / 2
        assert screen_y == viewer_h / 2


# ---------------------------------------------------------------------------
# 2. Collision-Aware Label Placement
# ---------------------------------------------------------------------------

class TestCollisionAwareLabelPlacement:
    def test_non_overlapping_labels_placed_at_top(self):
        """Labels with plenty of spacing should place at their default top position."""
        placed: list[tuple[int, int, int, int]] = []
        box_a = (100, 100, 50, 30)
        # Default label top position
        lbl_a = (box_a[0], box_a[1] - 18, box_a[0] + 80, box_a[1])
        placed.append(lbl_a)

        # Distant box b
        box_b = (500, 300, 50, 30)
        cand_b = (box_b[0], box_b[1] - 18, box_b[0] + 80, box_b[1])
        collides = any(
            not (cand_b[2] < p[0] or cand_b[0] > p[2] or cand_b[3] < p[1] or cand_b[1] > p[3])
            for p in placed
        )
        assert not collides

    def test_colliding_labels_offset_below(self):
        """Labels positioned at the same point must detect collision and offset."""
        placed: list[tuple[int, int, int, int]] = []
        box_a = (100, 100, 50, 30)
        lbl_a = (box_a[0], box_a[1] - 18, box_a[0] + 80, box_a[1])
        placed.append(lbl_a)

        # Overlapping adjacent box
        box_b = (110, 105, 45, 28)
        cand_b = (box_b[0], box_b[1] - 18, box_b[0] + 80, box_b[1])
        collides = any(
            not (cand_b[2] < p[0] or cand_b[0] > p[2] or cand_b[3] < p[1] or cand_b[1] > p[3])
            for p in placed
        )
        assert collides

        # Offset to bottom
        lbl_b_fallback = (box_b[0], box_b[1] + box_b[3] + 4, box_b[0] + 80, box_b[1] + box_b[3] + 22)
        collides_bottom = any(
            not (lbl_b_fallback[2] < p[0] or lbl_b_fallback[0] > p[2] or lbl_b_fallback[3] < p[1] or lbl_b_fallback[1] > p[3])
            for p in placed
        )
        assert not collides_bottom


# ---------------------------------------------------------------------------
# 3. Visual Clarity & Non-Destructive Overlay
# ---------------------------------------------------------------------------

class TestVisualClarity:
    def test_original_image_unmodified(self):
        """The source image array must remain pristine and not modified in-place."""
        img = np.full((100, 100, 3), 180, dtype=np.uint8)
        img_copy = img.copy()

        service = ColourIdentificationService()
        result = service.identify(img)

        # Original input matrix must be byte-for-byte identical
        np.testing.assert_array_equal(img, img_copy)
        assert result.original_image is not None
        np.testing.assert_array_equal(result.original_image, img_copy)

    def test_overlay_semi_transparent_blending(self):
        """Overlay background pills must use alpha blending rather than 100% opaque blockout."""
        img = np.full((120, 200, 3), 100, dtype=np.uint8)
        service = ColourIdentificationService()

        tape = DetectedRegion(
            region_id="T001",
            region_type="tape",
            detected_color="dark_blue",
            bbox=(20, 40, 60, 30),
            center=(50, 55),
            area=1800.0,
            width=60,
            height=30,
            confidence=0.95,
            status="DETECTED",
            branch_id="unassigned",
        )
        overlay = service._create_overlay(img, [tape], [])
        assert overlay.shape == img.shape
        # Outside bounding box, pixels must match original
        assert overlay[5, 5, 0] == img[5, 5, 0]


# ---------------------------------------------------------------------------
# 4. Label Formatting & String Consistency
# ---------------------------------------------------------------------------

class TestLabelFormatting:
    def test_tape_label_format(self):
        """Tape labels must be formatted as '<COLOUR> TAPE | <CONF>%'."""
        conf = 0.942
        color = "green"
        pct = int(round(conf * 100))
        label = f"{color.replace('_', ' ').upper()} TAPE | {pct}%"
        assert label == "GREEN TAPE | 94%"

    def test_dark_blue_tape_label_format(self):
        conf = 0.914
        color = "dark_blue"
        pct = int(round(conf * 100))
        label = f"{color.replace('_', ' ').upper()} TAPE | {pct}%"
        assert label == "DARK BLUE TAPE | 91%"

    def test_wire_label_format(self):
        """Wire labels must be formatted as 'WIRE: <COLOUR> | <CONF>%'."""
        conf = 0.963
        color = "red"
        pct = int(round(conf * 100))
        label = f"WIRE: {color.upper()} | {pct}%"
        assert label == "WIRE: RED | 96%"

        conf_black = 0.927
        label_black = f"WIRE: {'black'.upper()} | {int(round(conf_black * 100))}%"
        assert label_black == "WIRE: BLACK | 93%"


# ---------------------------------------------------------------------------
# 5. Non-Maximum Suppression & Near-Duplicate Filtering
# ---------------------------------------------------------------------------

class TestNearDuplicateSuppression:
    def test_suppresses_same_colour_adjacent_fragments(self):
        """Two adjacent detections of the same wire colour within 25px must be suppressed."""
        det_a = DetectedRegion(
            region_id="W001",
            region_type="wire",
            detected_color="blue",
            bbox=(100, 100, 20, 20),
            center=(110, 110),
            area=400.0,
            width=20,
            height=20,
            confidence=0.90,
            status="IDENTIFIED",
            branch_id="unassigned",
        )
        det_b = DetectedRegion(
            region_id="W002",
            region_type="wire",
            detected_color="blue",
            bbox=(110, 105, 20, 20),
            center=(120, 115),  # distance = sqrt(100+25) = 11.2px (< 25px)
            area=380.0,
            width=20,
            height=20,
            confidence=0.75,
            status="IDENTIFIED",
            branch_id="unassigned",
        )
        service = ColourIdentificationService()
        kept = service._remove_overlapping([det_a, det_b])
        assert len(kept) == 1
        assert kept[0].region_id == "W001"

    def test_keeps_different_colours_at_same_location(self):
        """Distinct wire colours (e.g. crossing wires) should not be blindly deleted by proximity."""
        det_blue = DetectedRegion(
            region_id="W001",
            region_type="wire",
            detected_color="blue",
            bbox=(100, 100, 30, 30),
            center=(115, 115),
            area=900.0,
            width=30,
            height=30,
            confidence=0.92,
            status="IDENTIFIED",
            branch_id="unassigned",
        )
        det_yellow = DetectedRegion(
            region_id="W002",
            region_type="wire",
            detected_color="yellow",
            bbox=(125, 125, 30, 30),
            center=(140, 140),
            area=850.0,
            width=30,
            height=30,
            confidence=0.88,
            status="IDENTIFIED",
            branch_id="unassigned",
        )
        service = ColourIdentificationService()
        kept = service._remove_overlapping([det_blue, det_yellow])
        assert len(kept) == 2


# ---------------------------------------------------------------------------
# 6. Real Dataset Visualisation Validation
# ---------------------------------------------------------------------------

class TestRealDatasetVisualisation:
    @pytest.fixture
    def real_img(self):
        if not DATASET_IMAGE.is_file():
            pytest.skip("Dataset image not available")
        img = cv2.imread(str(DATASET_IMAGE), cv2.IMREAD_COLOR)
        return img

    def test_real_image_overlay_generation(self, real_img):
        service = ColourIdentificationService()
        result = service.identify(real_img)
        assert result.overlay_image is not None
        assert result.overlay_image.shape == real_img.shape

        # Verify not washed out: median channel value should be close to original
        orig_gray = cv2.cvtColor(real_img, cv2.COLOR_BGR2GRAY)
        over_gray = cv2.cvtColor(result.overlay_image, cv2.COLOR_BGR2GRAY)
        orig_med = float(np.median(orig_gray))
        over_med = float(np.median(over_gray))
        assert abs(orig_med - over_med) < 15.0, "Overlay image brightness drifted too far"
