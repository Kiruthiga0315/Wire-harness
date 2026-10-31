"""Tests validating colour identification accuracy on real wire harness dataset images.

Verifies:
  1. Massive false positive reduction on background table (elimination of 400+ false detections).
  2. Suppression of false gray detections on the white table.
  3. Tape vs wire classification separation (no high-IoU overlaps).
  4. Evidence-based confidence spread (not locked to 56-59%, with >=80% high-tier detections).
  5. Correct corridor containment along harness skeleton.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.colour_identification_service import (
    ColourIdentificationService,
    _box_iou,
)

DATASET_DIR = Path(__file__).resolve().parent.parent / "data" / "test_images" / "images_001" / "001"


@pytest.fixture
def service() -> ColourIdentificationService:
    return ColourIdentificationService()


@pytest.fixture
def real_image():
    path = DATASET_DIR / "001_01_board_crop.png"
    if not path.is_file():
        pytest.skip(f"Dataset image not found: {path}")
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert img is not None
    return img


@pytest.fixture
def real_mask():
    path = DATASET_DIR / "001_03_harness_mask.png"
    if not path.is_file():
        pytest.skip(f"Harness mask not found: {path}")
    mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    assert mask is not None
    return mask


@pytest.fixture
def real_skeleton():
    path = DATASET_DIR / "001_06_skeleton.png"
    if not path.is_file():
        pytest.skip(f"Skeleton not found: {path}")
    skel = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    assert skel is not None
    return skel


class TestRealImageColourAccuracy:
    """Rigorous tests on real industrial harness images to prevent detection regression."""

    def test_real_image_with_mask_wire_count_and_no_explosion(
        self, service, real_image, real_mask, real_skeleton
    ):
        """Total wire detections should be dramatically reduced from baseline (426) to < 85."""
        result = service.identify(
            real_image,
            harness_mask=real_mask,
            skeleton=real_skeleton,
            inspection_id="acc-test-masked",
        )
        assert result.success

        total_wires = len(result.wire_detections)
        confident_wires = [d for d in result.wire_detections if d.status == "IDENTIFIED"]

        # Baseline was 426 wire regions; fixed pipeline should have < 85 total
        assert total_wires < 85, f"Excessive wire detections: {total_wires} (expected < 85)"
        # Should identify actual visible wires (not 0)
        assert len(confident_wires) >= 10, f"Too few confident wires: {len(confident_wires)}"

    def test_real_image_gray_wire_suppression(
        self, service, real_image, real_mask, real_skeleton
    ):
        """Gray wire detections on the board background must be strictly suppressed (baseline had 203)."""
        result = service.identify(
            real_image,
            harness_mask=real_mask,
            skeleton=real_skeleton,
            inspection_id="acc-test-gray",
        )
        gray_wires = [d for d in result.wire_detections if d.detected_color == "gray"]
        assert len(gray_wires) <= 30, f"Too many gray wires: {len(gray_wires)} (expected <= 30, was 203 in baseline)"

    def test_tape_wire_separation(
        self, service, real_image, real_mask, real_skeleton
    ):
        """Tape detections and wire detections must not heavily overlap."""
        result = service.identify(
            real_image,
            harness_mask=real_mask,
            skeleton=real_skeleton,
            inspection_id="acc-test-tape-sep",
        )
        assert len(result.tape_detections) > 0, "Expected tape detections"
        assert len(result.wire_detections) > 0, "Expected wire detections"

        # Check IoU between any tape detection and wire detection
        for tape in result.tape_detections:
            for wire in result.wire_detections:
                iou = _box_iou(tape.bbox, wire.bbox)
                assert iou < 0.35, f"Excessive overlap (IoU={iou:.2f}) between tape {tape.detected_color} and wire {wire.detected_color}"

    def test_confidence_spread_and_high_tier(
        self, service, real_image, real_mask, real_skeleton
    ):
        """Confidence scores must reflect evidence, not artificially cluster at 0.56-0.59."""
        result = service.identify(
            real_image,
            harness_mask=real_mask,
            skeleton=real_skeleton,
            inspection_id="acc-test-confidence",
        )
        confident_wires = [d for d in result.wire_detections if d.status == "IDENTIFIED"]
        confidences = [d.confidence for d in confident_wires]
        assert len(confidences) > 0

        # Mean confidence of identified wires should be >= 0.70 (not 0.56-0.59)
        mean_conf = float(np.mean(confidences))
        assert mean_conf >= 0.70, f"Mean confidence too low: {mean_conf:.3f} (expected >= 0.70)"

        # High tier (>= 0.80) detections must exist
        high_tier = [c for c in confidences if c >= 0.80]
        assert len(high_tier) >= 15, f"Expected at least 15 high-confidence wires, got {len(high_tier)}"

    def test_corridor_containment_near_skeleton(
        self, service, real_image, real_mask, real_skeleton
    ):
        """All confident wire detections must be within physical wire corridor distance of skeleton."""
        result = service.identify(
            real_image,
            harness_mask=real_mask,
            skeleton=real_skeleton,
            inspection_id="acc-test-corridor",
        )
        dist_transform = cv2.distanceTransform(
            cv2.bitwise_not(real_skeleton), cv2.DIST_L2, 3
        )
        for wire in result.wire_detections:
            if wire.status == "IDENTIFIED":
                cx, cy = wire.center
                dist = dist_transform[int(cy), int(cx)]
                # Centroid must be within max corridor radius (22 px) of skeleton
                assert dist <= 22.0, f"Wire detection at ({cx}, {cy}) is {dist:.1f}px away from skeleton"

    def test_standalone_board_crop_without_external_mask(
        self, service, real_image
    ):
        """When no external mask/skeleton is provided, pipeline should compute mask and prevent explosion."""
        result = service.identify(
            real_image,
            inspection_id="acc-test-standalone",
        )
        assert result.success
        total_detections = len(result.wire_detections) + len(result.tape_detections)
        # Should NOT produce 400+ detections on board (baseline was ~500)
        assert total_detections < 180, f"Standalone pipeline produced excessive detections: {total_detections}"
