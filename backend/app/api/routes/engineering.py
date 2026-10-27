from __future__ import annotations

import base64

import cv2
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.images import DEMO_IMAGE_LOGICAL_NAME, resolve_demo_image
from app.core.database import get_db
from app.models import Checkpoint
from app.schemas.color_inspection import (
    ColorInspectionRequest,
    ColorInspectionResponse,
    ColourVector,
    ROIInformation,
)
from app.schemas.segmentation import (
    SegmentationImages,
    SegmentationMetrics,
    SegmentationResponse,
)
from app.schemas.harness_graph import (
    BranchOrientationResponse,
    BranchPairDistanceResponse,
    GraphBranchResponse,
    GraphNodeResponse,
    GraphPointResponse,
    HarnessGraphImages,
    HarnessGraphMeasurements,
    HarnessGraphMetrics,
    HarnessGraphResponse,
    JunctionTerminalDistanceResponse,
)
from app.services.active_image_service import active_image_service
from app.services.color_inspection_service import ColorInspectionService
from app.services.harness_graph_service import HarnessGraphService
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray

router = APIRouter(prefix="/engineering", tags=["Engineering"])
segmentation_service = HarnessSegmentationService()
color_inspection_service = ColorInspectionService()
harness_graph_service = HarnessGraphService()


def _png_data_url(image: ImageArray) -> str:
    encoded, png = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("OpenCV could not encode a segmentation output")
    payload = base64.b64encode(png.tobytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


@router.post(
    "/segmentation/demo",
    response_model=SegmentationResponse,
    summary="Run experimental segmentation on the configured harness image",
)
def segment_demo_image() -> SegmentationResponse:
    active = active_image_service.get_active_image()
    try:
        result = segmentation_service.segment(active.bgr_image)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Segmentation failed: {exc}") from exc

    return SegmentationResponse(
        source_image=active.filename,
        method="OpenCV grayscale + inverted Otsu threshold + morphological closing + connected-component filtering",
        production_ready=False,
        disclaimer=(
            "Engineering feasibility output only. This is not the final production "
            "segmentation algorithm and has not been validated for inspection decisions."
        ),
        metrics=SegmentationMetrics(
            harness_occupied_percentage=result.occupied_percentage,
            contour_count=result.contour_count,
            otsu_threshold=result.otsu_threshold,
            removed_component_count=result.removed_component_count,
            excluded_border_component_count=result.excluded_border_component_count,
            image_width=result.image_width,
            image_height=result.image_height,
        ),
        images=SegmentationImages(
            binary_mask=_png_data_url(result.binary_mask),
            contour_image=_png_data_url(result.contour_image),
            skeleton_image=_png_data_url(result.skeleton_image),
        ),
    )


@router.post(
    "/color-inspection",
    response_model=ColorInspectionResponse,
    summary="Inspect colour within a configured checkpoint ROI",
)
def inspect_checkpoint_colour(
    payload: ColorInspectionRequest,
    db: Session = Depends(get_db),
) -> ColorInspectionResponse:
    checkpoint = db.scalar(
        select(Checkpoint).where(
            Checkpoint.model_id == payload.model_id,
            Checkpoint.checkpoint_id == payload.checkpoint_id,
        )
    )
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    if not checkpoint.expected_value:
        raise HTTPException(status_code=422, detail="Checkpoint has no expected colour")

    active = active_image_service.get_active_image()
    image = active.bgr_image

    try:
        result = color_inspection_service.inspect(
            image,
            expected_colour=checkpoint.expected_value,
            center_x=checkpoint.reference_x,
            center_y=checkpoint.reference_y,
            roi_width=checkpoint.roi_width,
            roi_height=checkpoint.roi_height,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return ColorInspectionResponse(
        model_id=checkpoint.model_id,
        checkpoint_id=checkpoint.checkpoint_id,
        checkpoint_name=checkpoint.checkpoint_name,
        expected_colour=result.expected_colour,
        detected_colour=result.detected_colour,
        mean_hsv=ColourVector(
            channel_1=result.mean_hsv[0],
            channel_2=result.mean_hsv[1],
            channel_3=result.mean_hsv[2],
        ),
        mean_lab=ColourVector(
            channel_1=result.mean_lab[0],
            channel_2=result.mean_lab[1],
            channel_3=result.mean_lab[2],
        ),
        confidence=result.confidence,
        status=result.status,
        roi=ROIInformation(
            x=result.roi.x,
            y=result.roi.y,
            width=result.roi.width,
            height=result.roi.height,
        ),
        debug_roi_image=_png_data_url(result.roi.image) if payload.debug else None,
        disclaimer=(
            "Development colour feasibility result only. Production use requires controlled "
            "lighting, camera colour calibration, and validated model-specific thresholds."
        ),
    )


@router.post(
    "/harness-graph/demo",
    response_model=HarnessGraphResponse,
    summary="Analyse experimental skeleton endpoints and junctions",
)
def analyse_demo_harness_graph() -> HarnessGraphResponse:
    active = active_image_service.get_active_image()
    image = active.bgr_image

    try:
        segmentation = segmentation_service.segment(image)
        graph = harness_graph_service.analyse(
            segmentation.binary_mask,
            base_image=image,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Harness graph analysis failed: {exc}") from exc

    return HarnessGraphResponse(
        source_image=active.filename,
        production_ready=False,
        disclaimer=(
            "Feasibility analysis only. Endpoint, junction, branch, orientation, and pixel-distance "
            "results depend on the experimental segmentation and must not be used for production "
            "PASS/NG decisions. Pixel-to-millimetre calibration has not been applied."
        ),
        metrics=HarnessGraphMetrics(
            endpoint_count=len(graph.endpoints),
            candidate_junction_pixel_count=graph.candidate_junction_pixel_count,
            clustered_junction_count=len(graph.junctions),
            skeleton_pixel_count=graph.skeleton_pixel_count,
            neighbour_connectivity=8,
            junction_cluster_radius=harness_graph_service.junction_cluster_radius,
            total_wire_length_pixels=graph.total_wire_length_pixels,
            extracted_branch_length_pixels=graph.extracted_branch_length_pixels,
            extracted_branch_count=len(graph.branches),
            topology_terminal_count=sum(
                node.node_type == "END_TERMINAL" for node in graph.nodes
            ),
            unresolved_segment_count=graph.unresolved_segment_count,
        ),
        endpoints=[GraphPointResponse(x=point.x, y=point.y) for point in graph.endpoints],
        junctions=[GraphPointResponse(x=point.x, y=point.y) for point in graph.junctions],
        measurements=HarnessGraphMeasurements(
            length_method=(
                "8-connected skeleton centreline: orthogonal step = 1 px; "
                "diagonal step = sqrt(2) px"
            ),
            orientation_convention=(
                "Clockwise image coordinates: 0 degrees = right, 90 = down, "
                "180 = left, 270 = up"
            ),
            branch_distance_definition=(
                "Branch-to-branch distance is measured between branch midpoints, "
                "both through their common junction and as a straight pixel distance"
            ),
            nodes=[
                GraphNodeResponse(
                    node_id=node.node_id,
                    node_type=node.node_type,
                    x=node.point.x,
                    y=node.point.y,
                    branch_count=node.branch_count,
                    branch_orientations=[
                        BranchOrientationResponse(
                            branch_id=orientation.branch_id,
                            angle_degrees=orientation.angle_degrees,
                        )
                        for orientation in node.branch_orientations
                    ],
                )
                for node in graph.nodes
            ],
            node_to_node_distances=[
                GraphBranchResponse(
                    branch_id=branch.branch_id,
                    source_node_id=branch.source_node_id,
                    target_node_id=branch.target_node_id,
                    path_length_pixels=branch.path_length_pixels,
                    straight_distance_pixels=branch.straight_distance_pixels,
                    orientation_degrees=branch.orientation_degrees,
                )
                for branch in graph.branches
            ],
            nearest_junction_to_terminal_distances=[
                JunctionTerminalDistanceResponse(
                    junction_node_id=distance.junction_node_id,
                    terminal_node_id=distance.terminal_node_id,
                    path_distance_pixels=distance.path_distance_pixels,
                    straight_distance_pixels=distance.straight_distance_pixels,
                )
                for distance in graph.junction_terminal_distances
            ],
            branch_to_branch_distances=[
                BranchPairDistanceResponse(
                    junction_node_id=distance.junction_node_id,
                    first_branch_id=distance.first_branch_id,
                    second_branch_id=distance.second_branch_id,
                    via_junction_distance_pixels=distance.via_junction_distance_pixels,
                    midpoint_straight_distance_pixels=(
                        distance.midpoint_straight_distance_pixels
                    ),
                    angular_separation_degrees=distance.angular_separation_degrees,
                )
                for distance in graph.branch_pair_distances
            ],
        ),
        images=HarnessGraphImages(
            skeleton_image=_png_data_url(graph.skeleton_image),
            graph_overlay=_png_data_url(graph.overlay_image),
        ),
    )
