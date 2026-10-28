import asyncio

import cv2
import httpx
import numpy as np

from app.main import app
from app.services.harness_graph_service import HarnessGraphService


def test_t_shape_has_three_endpoints_and_one_clustered_junction() -> None:
    mask = np.zeros((101, 101), dtype=np.uint8)
    cv2.line(mask, (20, 25), (80, 25), 255, 7)
    cv2.line(mask, (50, 25), (50, 80), 255, 7)

    result = HarnessGraphService(junction_cluster_radius=5).analyse(mask)

    assert {(point.x, point.y) for point in result.endpoints} == {
        (20, 25),
        (80, 25),
        (50, 80),
    }
    assert result.candidate_junction_pixel_count > 1
    assert len(result.junctions) == 1
    assert abs(result.junctions[0].x - 50) <= 1
    assert abs(result.junctions[0].y - 25) <= 1
    assert result.skeleton_pixel_count > 0
    assert result.skeleton_image.shape == mask.shape
    assert result.overlay_image.shape == (101, 101, 3)
    assert len(result.branches) == 3
    assert result.unresolved_segment_count == 0
    assert round(result.extracted_branch_length_pixels, 1) == 115.0
    junction_node = next(node for node in result.nodes if node.node_type == "JUNCTION")
    assert junction_node.branch_count == 3
    assert {round(item.angle_degrees) for item in junction_node.branch_orientations} == {
        0,
        90,
        180,
    }
    assert len(result.junction_terminal_distances) == 1
    assert len(result.branch_pair_distances) == 3


def test_graph_api_returns_candidate_coordinates_and_images() -> None:
    async def request_graph() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/api/engineering/harness-graph/demo")

    response = asyncio.run(request_graph())

    assert response.status_code == 200
    payload = response.json()
    assert payload["production_ready"] is False
    assert payload["unit"] == "cm"
    assert payload["pixels_per_cm"] > 0
    assert payload["metrics"]["total_wire_length_cm"] > 0
    assert payload["metrics"]["extracted_branch_length_cm"] > 0
    assert payload["metrics"]["endpoint_count"] == len(payload["endpoints"])
    assert payload["metrics"]["clustered_junction_count"] == len(payload["junctions"])
    assert payload["metrics"]["endpoint_count"] > 0
    assert payload["metrics"]["candidate_junction_pixel_count"] > 0
    assert payload["metrics"]["total_wire_length_pixels"] > 0
    assert payload["metrics"]["extracted_branch_count"] == len(
        payload["measurements"]["node_to_node_distances"]
    )
    first_branch = payload["measurements"]["node_to_node_distances"][0]
    assert first_branch["path_length_cm"] > 0
    assert first_branch["straight_distance_cm"] > 0
    first_j_dist = payload["measurements"]["nearest_junction_to_terminal_distances"][0]
    assert first_j_dist["path_distance_cm"] > 0
    first_b_dist = payload["measurements"]["branch_to_branch_distances"][0]
    assert first_b_dist["via_junction_distance_cm"] > 0

    assert payload["sheet_specification"] is not None
    assert payload["sheet_specification"]["total_terminals"] == 41
    assert payload["sheet_specification"]["total_junctions"] == 31
    assert payload["sheet_specification"]["total_nodes"] == 12
    assert len(payload["sheet_specification"]["node_distances"]) == 6
    assert len(payload["sheet_specification"]["junction_measurements"]) == 47

    assert "physical_verifications" in payload
    assert len(payload["physical_verifications"]) > 0
    first_pv = payload["physical_verifications"][0]
    assert first_pv["checkpoint_id"] == "CP-T01"
    assert first_pv["expected_distance_cm"] == 39.0
    assert first_pv["detected_distance_cm"] is not None
    assert first_pv["status"] in ("PASS", "REVIEW", "FAIL")

    assert payload["verification_summary"] is not None
    assert payload["verification_summary"]["total_checkpoints"] == len(payload["physical_verifications"])
    assert payload["verification_summary"]["pixels_per_cm"] > 0

    assert payload["measurements"]["nodes"]
    assert payload["measurements"]["nearest_junction_to_terminal_distances"]
    assert payload["measurements"]["branch_to_branch_distances"]
    assert payload["images"]["skeleton_image"].startswith("data:image/png;base64,")
    assert payload["images"]["graph_overlay"].startswith("data:image/png;base64,")
