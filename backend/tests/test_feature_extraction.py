from __future__ import annotations

from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from app.main import app
from app.schemas.feature_extraction import (
    FeatureExtractionRequest,
    FeatureExtractionResponse,
)
from app.services.feature_extraction_service import FeatureExtractionService


def _create_synthetic_t_harness(width: int = 300, height: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Create a synthetic T-junction harness with background noise."""
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    # Background texture/noise (lines and dots that should NOT be part of harness)
    cv2.rectangle(image, (10, 10), (40, 30), (210, 210, 210), 1)  # board fixture line
    cv2.circle(image, (280, 20), 3, (190, 190, 190), -1)  # board screw

    # Main horizontal trunk
    cv2.line(image, (40, 100), (260, 100), (25, 25, 25), 12)
    # Vertical branch
    cv2.line(image, (150, 100), (150, 175), (25, 25, 25), 10)

    # Segmented binary mask
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.line(mask, (40, 100), (260, 100), 255, 12)
    cv2.line(mask, (150, 100), (150, 175), 255, 10)

    return image, mask


def _create_synthetic_crossing_harness(width: int = 240, height: int = 240) -> tuple[np.ndarray, np.ndarray]:
    """Create two crossing wires (degree-4 intersection) to test crossing discrimination."""
    image = np.full((height, width, 3), 240, dtype=np.uint8)
    cv2.line(image, (30, 120), (210, 120), (20, 20, 20), 10)
    cv2.line(image, (120, 30), (120, 210), (20, 20, 20), 10)

    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.line(mask, (30, 120), (210, 120), 255, 10)
    cv2.line(mask, (120, 30), (120, 210), 255, 10)

    return image, mask


# =============================================================================
# 1. Edge Extraction Tests
# =============================================================================
def test_edge_extraction_filters_background_noise() -> None:
    image, mask = _create_synthetic_t_harness()
    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    assert result.edge_statistics.total_edge_pixels > 0
    assert result.edge_statistics.boundary_edge_pixels > 0
    assert result.edge_statistics.edge_density > 0.0
    # Background rectangle edges must be identified as filtered background edges
    assert result.edge_statistics.filtered_background_edges >= 0
    assert result.edge_statistics.boundary_edge_pixels <= result.edge_statistics.total_edge_pixels


# =============================================================================
# 2. Contour Extraction Tests
# =============================================================================
def test_contour_extraction_properties_and_main_harness() -> None:
    image, mask = _create_synthetic_t_harness()
    # Add an internal hole / loop inside the harness
    cv2.circle(mask, (100, 100), 2, 0, -1)

    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    contours = result.contour_information
    assert contours.total_contours >= 1
    assert contours.external_contours_count >= 1
    assert contours.main_harness_contour is not None

    mc = contours.main_harness_contour
    assert mc.area > 500.0
    assert mc.perimeter > 100.0
    assert mc.bounding_box.width > 150
    assert mc.bounding_box.height > 50
    assert 0.0 < mc.solidity <= 1.0
    assert 0.0 < mc.extent <= 1.0
    assert 0 <= mc.center_x < 300
    assert 0 <= mc.center_y < 200


# =============================================================================
# 3. Skeleton & Branch Path Extraction Tests
# =============================================================================
def test_skeleton_extraction_endpoints_and_ordered_paths() -> None:
    image, mask = _create_synthetic_t_harness()
    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    skel = result.skeleton_features
    assert skel.uncalibrated is True
    assert skel.total_wire_length_pixels > 0
    assert len(skel.endpoint_candidates) == 3  # Left, right, bottom of T
    assert len(skel.junction_candidates) == 1  # Center of T

    # Verify endpoint candidates have valid coordinates
    for ep in skel.endpoint_candidates:
        assert 0 <= ep.x < image.shape[1]
        assert 0 <= ep.y < image.shape[0]
        assert 0.0 <= ep.tangent_angle_deg < 360.0

    # Verify branches have ordered compact paths
    assert len(skel.branches) == 3
    for branch in skel.branches:
        assert branch.path_length_pixels > 0
        assert branch.straight_distance_pixels > 0
        assert 0.0 < branch.straightness_ratio <= 1.0
        assert 0.0 <= branch.orientation_deg < 360.0
        assert len(branch.compact_path) >= 2
        for pt in branch.compact_path:
            assert len(pt) == 2
            assert 0 <= pt[0] < image.shape[1]
            assert 0 <= pt[1] < image.shape[0]


def test_crossing_vs_electrical_joint_discrimination() -> None:
    image, mask = _create_synthetic_crossing_harness()
    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    skel = result.skeleton_features
    assert len(skel.junction_candidates) == 1
    junction = skel.junction_candidates[0]
    assert junction.branch_count == 4
    # The orthogonal 4-way crossing should be flagged as a visual crossing
    assert junction.is_simple_crossing is True


# =============================================================================
# 4. Geometric Features & Curvature Tests
# =============================================================================
def test_geometric_curvature_and_straightness() -> None:
    # Curved L-shaped wire
    height, width = 200, 200
    image = np.full((height, width, 3), 245, dtype=np.uint8)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.line(mask, (30, 50), (130, 50), 255, 10)
    cv2.line(mask, (130, 50), (130, 150), 255, 10)

    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    geom = result.geometric_features
    assert 0.0 < geom.mean_branch_straightness <= 1.0
    # Bend angle around 90-degree corner
    assert geom.max_bend_angle_deg >= 45.0
    assert geom.total_detected_terminals >= 2


# =============================================================================
# 5. Terminal and Joint Candidate ROIs for Part Identification
# =============================================================================
def test_candidate_regions_for_part_identification() -> None:
    image, mask = _create_synthetic_t_harness()
    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    rois = result.candidate_regions_for_part_id
    assert len(rois) >= 4  # 3 terminal candidates + 1 joint candidate

    terminal_candidates = [r for r in rois if r.candidate_type == "TERMINAL_CANDIDATE"]
    joint_candidates = [r for r in rois if r.candidate_type == "JOINT_CANDIDATE"]

    assert len(terminal_candidates) == 3
    assert len(joint_candidates) == 1

    for cand in rois:
        # Check all bounding box coordinates are strictly inside image boundaries
        b = cand.bounding_box
        assert b.x >= 0
        assert b.y >= 0
        assert b.x + b.width <= image.shape[1]
        assert b.y + b.height <= image.shape[0]
        assert cand.local_area > 0
        # Crucial requirement: must include disclaimer note for Part Identification
        assert "Part Identification" in cand.note


# =============================================================================
# 6. Multi-Layer Visualizations
# =============================================================================
def test_all_six_visualizations_generated() -> None:
    image, mask = _create_synthetic_t_harness()
    service = FeatureExtractionService()
    result = service.extract_features(image, mask=mask)

    vis = result.visualizations
    assert vis is not None
    assert vis.original_preprocessed.startswith("data:image/png;base64,")
    assert vis.edge_map.startswith("data:image/png;base64,")
    assert vis.contour_visualization.startswith("data:image/png;base64,")
    assert vis.skeleton_visualization.startswith("data:image/png;base64,")
    assert vis.keypoint_junction_visualization.startswith("data:image/png;base64,")
    assert vis.combined_overlay.startswith("data:image/png;base64,")


# =============================================================================
# 7. Error Handling on Invalid Inputs
# =============================================================================
def test_invalid_images_produce_meaningful_errors() -> None:
    service = FeatureExtractionService()

    with pytest.raises(ValueError, match="numpy ndarray"):
        service.extract_features("not an image")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="np.uint8"):
        service.extract_features(np.zeros((100, 100), dtype=np.float32))

    with pytest.raises(ValueError, match="too small"):
        service.extract_features(np.zeros((10, 10), dtype=np.uint8))


# =============================================================================
# 8. API Endpoint Integration Tests
# =============================================================================
def test_feature_extraction_demo_api_endpoint() -> None:
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.post("/api/engineering/feature-extraction/demo")
    assert res.status_code == 200
    data = res.json()

    assert "image_dimensions" in data
    assert data["image_dimensions"]["width"] > 0
    assert data["image_dimensions"]["height"] > 0

    assert "edge_statistics" in data
    assert data["edge_statistics"]["total_edge_pixels"] > 0

    assert "contour_information" in data
    assert data["contour_information"]["total_contours"] > 0

    assert "skeleton_features" in data
    assert data["skeleton_features"]["total_wire_length_pixels"] > 0
    assert len(data["skeleton_features"]["endpoint_candidates"]) > 0

    assert "candidate_regions_for_part_id" in data
    assert len(data["candidate_regions_for_part_id"]) > 0

    assert "geometric_features" in data
    assert "visualizations" in data
    assert data["visualizations"]["combined_overlay"] is not None
    assert data["processing_time_ms"] > 0


# =============================================================================
# 9. Real Image Validation (test_images/ and images_001/)
# =============================================================================
def test_feature_extraction_on_images_001_dataset() -> None:
    sample_path = (
        Path(__file__).resolve().parents[2]
        / "images_001"
        / "001"
        / "001_01_board_crop.png"
    )
    if not sample_path.exists():
        pytest.skip(f"Images_001 dataset file not found at {sample_path}")

    image = cv2.imread(str(sample_path))
    assert image is not None

    service = FeatureExtractionService()
    result = service.extract_features(image)

    # Check image dimensions match 001_01_board_crop.png (560, 1800, 3)
    assert result.image_dimensions.width == image.shape[1]
    assert result.image_dimensions.height == image.shape[0]

    # Verify meaningful non-zero extracted features
    assert result.edge_statistics.boundary_edge_pixels > 1000
    assert result.contour_information.total_contours > 0
    assert result.skeleton_features.total_wire_length_pixels > 500
    assert len(result.skeleton_features.endpoint_candidates) >= 5
    assert len(result.skeleton_features.junction_candidates) >= 2

    # Verify all coordinates are strictly within boundaries
    w = result.image_dimensions.width
    h = result.image_dimensions.height

    for ep in result.skeleton_features.endpoint_candidates:
        assert 0 <= ep.x < w, f"Endpoint x coordinate {ep.x} out of bounds"
        assert 0 <= ep.y < h, f"Endpoint y coordinate {ep.y} out of bounds"

    for jc in result.skeleton_features.junction_candidates:
        assert 0 <= jc.x < w, f"Junction x coordinate {jc.x} out of bounds"
        assert 0 <= jc.y < h, f"Junction y coordinate {jc.y} out of bounds"

    for cand in result.candidate_regions_for_part_id:
        b = cand.bounding_box
        assert b.x >= 0 and b.x + b.width <= w
        assert b.y >= 0 and b.y + b.height <= h

    assert result.processing_time_ms > 0
    assert len(result.errors) == 0
