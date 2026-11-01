from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.schemas.feature_extraction import FeatureExtractionRequest
from app.services.feature_extraction_service import FeatureExtractionService
from app.services.harness_segmentation_service import HarnessSegmentationService
from app.services.image_preprocessing_service import ImagePreprocessingService


@pytest.fixture
def preprocessing_service() -> ImagePreprocessingService:
    return ImagePreprocessingService(min_resolution=(64, 64))


@pytest.fixture
def segmentation_service() -> HarnessSegmentationService:
    return HarnessSegmentationService()


@pytest.fixture
def feature_extraction_service() -> FeatureExtractionService:
    return FeatureExtractionService()


def test_image_preprocessing_quality_assessment(preprocessing_service: ImagePreprocessingService):
    """Test blur, brightness, contrast, and quality status assessment."""
    # 1. Normal contrast and sharp image
    normal_img = np.full((200, 300, 3), 200, dtype=np.uint8)
    cv2.circle(normal_img, (150, 100), 40, (30, 30, 30), -1)
    cv2.line(normal_img, (20, 100), (280, 100), (0, 0, 0), 4)

    metrics = preprocessing_service.assess_quality(normal_img)
    assert metrics.quality_status == "PASS"
    assert not metrics.is_blurry
    assert not metrics.is_underexposed
    assert not metrics.is_overexposed

    # 2. Blurry image
    blurred_img = cv2.GaussianBlur(normal_img, (35, 35), 15.0)
    blur_metrics = preprocessing_service.assess_quality(blurred_img)
    assert blur_metrics.is_blurry
    assert blur_metrics.quality_status in ("REVIEW", "REJECT")


def test_image_preprocessing_vertical_orientation_correction(preprocessing_service: ImagePreprocessingService):
    """Test auto-rotation when an image is captured in portrait/vertical orientation."""
    # Create portrait image (height > 1.35 * width)
    portrait_img = np.full((400, 200, 3), 220, dtype=np.uint8)
    res = preprocessing_service.preprocess(portrait_img)

    assert res.rotation_applied_deg == 90
    assert res.processed_dimensions[0] >= res.processed_dimensions[1]  # Horizontal layout


def test_harness_segmentation_suppresses_board_text(segmentation_service: HarnessSegmentationService):
    """Test that printed inspection board markings, text, and fixture lines are suppressed."""
    # Create white inspection board background
    img = np.full((300, 600, 3), 245, dtype=np.uint8)

    # Draw continuous wire harness trunk and branch (dark lines)
    cv2.line(img, (50, 150), (550, 150), (35, 35, 35), 6)  # Main trunk
    cv2.line(img, (250, 150), (250, 60), (35, 35, 35), 4)   # Branch 1
    cv2.line(img, (400, 150), (400, 240), (20, 120, 20), 4) # Branch 2 (green wire)

    # Add printed board text (e.g. "PA BOARD NO: 2", "J1", "T01") isolated away from wires
    cv2.putText(img, "PA BOARD NO: 2", (60, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2)
    cv2.putText(img, "J1", (270, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 2)
    cv2.putText(img, "T01", (60, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 2)

    result = segmentation_service.segment(img)

    assert result.binary_mask is not None
    assert result.occupied_percentage > 0.5

    # Check that the wire trunk at (300, 150) is detected (white 255)
    assert result.binary_mask[150, 300] == 255

    # Check that isolated printed board text at (60, 40) is suppressed (black 0)
    assert result.binary_mask[40, 60] == 0
    assert result.binary_mask[260, 60] == 0

    # Verify isolated harness image has clean white background where text was
    assert tuple(result.isolated_harness_image[40, 60]) == (255, 255, 255)


def test_universal_feature_extraction_end_to_end(feature_extraction_service: FeatureExtractionService):
    """Verify feature extraction extracts 10 visualization layers, geometry, and quality summary."""
    # Synthesize test harness workpiece
    img = np.full((250, 500, 3), 235, dtype=np.uint8)
    cv2.line(img, (60, 125), (440, 125), (30, 30, 30), 6)   # Trunk
    cv2.line(img, (200, 125), (200, 50), (160, 40, 30), 4)  # Branch A (blue-ish)
    cv2.line(img, (350, 125), (350, 200), (30, 140, 30), 4) # Branch B (green)

    response = feature_extraction_service.extract_features(
        img,
        config=FeatureExtractionRequest(generate_visualizations=True),
    )

    # 1. Dimensions
    assert response.image_dimensions.width == 500
    assert response.image_dimensions.height == 250

    # 2. Quality Control
    assert response.quality_control is not None
    assert response.quality_control.quality_status in ("PASS", "REVIEW")
    assert response.quality_control.segmentation_confidence >= 0.70
    assert response.quality_control.endpoints_count >= 2

    # 3. Skeleton & Centerlines
    assert response.skeleton_features.total_wire_length_pixels > 100.0
    assert len(response.skeleton_features.branches) >= 2

    # 4. Wire width estimation
    assert response.geometric_features.mean_estimated_wire_width_pixels > 0.0

    # 5. 10 Diagnostic Engineering Visualizations
    vis = response.visualizations
    assert vis is not None
    assert vis.original_image is not None
    assert vis.preprocessed_image is not None
    assert vis.segmentation_overlay is not None
    assert vis.binary_mask is not None
    assert vis.isolated_harness is not None
    assert vis.contour_visualization is not None
    assert vis.skeleton_visualization is not None
    assert vis.endpoints_junctions_visualization is not None
    assert vis.branch_paths_visualization is not None
    assert vis.feature_extraction_results is not None


def test_empty_or_no_harness_triggers_reject_or_review(feature_extraction_service: FeatureExtractionService):
    """Verify that an image with no detectable wire harness triggers non-PASS status with clear reasons."""
    blank_white = np.full((200, 300, 3), 250, dtype=np.uint8)

    response = feature_extraction_service.extract_features(blank_white)
    assert response.quality_control is not None
    assert response.quality_control.quality_status in ("REVIEW", "REJECT")
    assert len(response.quality_control.reasons_for_review_or_reject) > 0
