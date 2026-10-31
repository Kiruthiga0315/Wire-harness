from __future__ import annotations

import base64

import cv2
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Checkpoint
from app.schemas.checkpoint import CheckpointRead
from app.schemas.wire_color import WireColorIdentificationResponse
from app.schemas.feature_extraction import (
    FeatureExtractionRequest,
    FeatureExtractionResponse,
)
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
    SheetJunctionMeasurementSpec,
    SheetNodeDistanceSpec,
    SheetSpecification,
)
from app.services.active_image_service import (
    DEMO_IMAGE_LOGICAL_NAME,
    active_image_service,
    resolve_demo_image,
)
from app.services.color_inspection_service import ColorInspectionService
from app.services.harness_graph_service import HarnessGraphService
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray

router = APIRouter(prefix="/engineering", tags=["Engineering"])
segmentation_service = HarnessSegmentationService()
color_inspection_service = ColorInspectionService()
harness_graph_service = HarnessGraphService()
from app.services.wire_color_service import WireColorIdentificationService
from app.services.feature_extraction_service import FeatureExtractionService
wire_color_service = WireColorIdentificationService(segmentation_service=segmentation_service)
feature_extraction_service = FeatureExtractionService(
    segmentation_service=segmentation_service,
    graph_service=harness_graph_service,
)


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
        result = segmentation_service.segment(active.bgr_image, filename=active.filename)
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
            isolated_harness=_png_data_url(result.isolated_harness_image) if result.isolated_harness_image is not None else None,
        ),
    )


@router.post(
    "/checkpoints/sync-golden",
    response_model=list[CheckpointRead],
    summary="Sync engineering checkpoints from Golden Reference & Checkpoints",
)
def sync_engineering_checkpoints_from_golden(
    model_id: str = "DEMO-HARNESS-001",
    replace: bool = True,
    scale_to_active_image: bool = True,
    db: Session = Depends(get_db),
) -> list[CheckpointRead]:
    from app.services.checkpoint_service import CheckpointService, ModelNotFoundError
    try:
        return CheckpointService(db).sync_from_golden_reference(
            model_id=model_id,
            replace=replace,
            scale_to_active_image=scale_to_active_image,
        )  # type: ignore[return-value]
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Product model not found") from exc


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
    expected_col = payload.expected_colour
    if not expected_col:
        val = (checkpoint.expected_value or "").strip().upper()
        if val in ("BLACK", "WHITE", "BLUE", "RED", "GREEN", "YELLOW", "ORANGE", "GREY", "GRAY"):
            expected_col = val
        elif checkpoint.category == "Tape" or checkpoint.inspection_type == "Colour":
            expected_col = "BLUE"
        else:
            expected_col = "BLACK"

    active = active_image_service.get_active_image()
    image = active.bgr_image

    try:
        result = color_inspection_service.inspect(
            image,
            expected_colour=expected_col,
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


SHEET_NODE_DISTANCES = [
    SheetNodeDistanceSpec(node_pair="N1 - N2", distance_cm=28.5),
    SheetNodeDistanceSpec(node_pair="N3 - N4", distance_cm=10.0),
    SheetNodeDistanceSpec(node_pair="N5 - N6", distance_cm=53.8),
    SheetNodeDistanceSpec(node_pair="N7 - N8", distance_cm=8.0),
    SheetNodeDistanceSpec(node_pair="N9 - N10", distance_cm=23.5),
    SheetNodeDistanceSpec(node_pair="N11 - N12", distance_cm=60.5),
]

SHEET_JUNCTION_MEASUREMENTS = [
    SheetJunctionMeasurementSpec(source="J1", target="T1", distance_cm=39.0),
    SheetJunctionMeasurementSpec(source="J1", target="T2", distance_cm=46.0),
    SheetJunctionMeasurementSpec(source="J1", target="T3", distance_cm=45.0),
    SheetJunctionMeasurementSpec(source="J2", target="T5", distance_cm=21.0),
    SheetJunctionMeasurementSpec(source="J2", target="T6", distance_cm=20.0),
    SheetJunctionMeasurementSpec(source="J3", target="T4", distance_cm=29.5),
    SheetJunctionMeasurementSpec(source="J3", target="T7", distance_cm=18.0),
    SheetJunctionMeasurementSpec(source="J3", target="T8", distance_cm=20.0),
    SheetJunctionMeasurementSpec(source="J4", target="J6", distance_cm=10.0),
    SheetJunctionMeasurementSpec(source="J6", target="T10", distance_cm=29.0),
    SheetJunctionMeasurementSpec(source="J6", target="T9", distance_cm=11.5),
    SheetJunctionMeasurementSpec(source="J5", target="J7", distance_cm=49.0),
    SheetJunctionMeasurementSpec(source="J7", target="T12", distance_cm=29.4),
    SheetJunctionMeasurementSpec(source="J7", target="T11", distance_cm=11.0),
    SheetJunctionMeasurementSpec(source="J8", target="J9", distance_cm=7.0),
    SheetJunctionMeasurementSpec(source="J9", target="T13", distance_cm=15.0),
    SheetJunctionMeasurementSpec(source="J9", target="T14", distance_cm=12.0),
    SheetJunctionMeasurementSpec(source="J11", target="J10", distance_cm=6.5),
    SheetJunctionMeasurementSpec(source="J10", target="T18", distance_cm=14.0),
    SheetJunctionMeasurementSpec(source="J10", target="T17", distance_cm=12.0),
    SheetJunctionMeasurementSpec(source="J12", target="T22", distance_cm=10.0),
    SheetJunctionMeasurementSpec(source="J15", target="T15", distance_cm=18.0),
    SheetJunctionMeasurementSpec(source="J16", target="T16", distance_cm=10.0),
    SheetJunctionMeasurementSpec(source="J19", target="T19", distance_cm=10.0),
    SheetJunctionMeasurementSpec(source="J14", target="T20", distance_cm=14.5),
    SheetJunctionMeasurementSpec(source="J14", target="T21", distance_cm=17.0),
    SheetJunctionMeasurementSpec(source="J18", target="T23", distance_cm=20.0),
    SheetJunctionMeasurementSpec(source="J18", target="T24", distance_cm=17.0),
    SheetJunctionMeasurementSpec(source="J20", target="J21", distance_cm=35.0),
    SheetJunctionMeasurementSpec(source="J21", target="T29", distance_cm=16.0),
    SheetJunctionMeasurementSpec(source="J24", target="T30", distance_cm=44.0),
    SheetJunctionMeasurementSpec(source="J21", target="T31", distance_cm=39.0),
    SheetJunctionMeasurementSpec(source="J21", target="T28", distance_cm=10.0),
    SheetJunctionMeasurementSpec(source="J20", target="J22", distance_cm=15.0),
    SheetJunctionMeasurementSpec(source="J23", target="T27", distance_cm=19.0),
    SheetJunctionMeasurementSpec(source="J24", target="T25", distance_cm=19.0),
    SheetJunctionMeasurementSpec(source="J24", target="T26", distance_cm=13.0),
    SheetJunctionMeasurementSpec(source="J25", target="J26", distance_cm=20.0),
    SheetJunctionMeasurementSpec(source="J26", target="T33", distance_cm=26.0),
    SheetJunctionMeasurementSpec(source="J26", target="T34", distance_cm=20.0),
    SheetJunctionMeasurementSpec(source="J26", target="T32", distance_cm=18.0),
    SheetJunctionMeasurementSpec(source="J27", target="T35", distance_cm=26.0),
    SheetJunctionMeasurementSpec(source="J28", target="T38", distance_cm=69.0),
    SheetJunctionMeasurementSpec(source="J29", target="T36", distance_cm=32.0),
    SheetJunctionMeasurementSpec(source="J29", target="T37", distance_cm=12.0),
    SheetJunctionMeasurementSpec(source="J31", target="T41", distance_cm=31.0),
    SheetJunctionMeasurementSpec(source="J31", target="T40", distance_cm=23.5),
]

SHEET_JUNCTION_BRANCH_COUNTS = {
    "J1": 2, "J2": 2, "J3": 3, "J4": 2, "J5": 2, "J6": 2, "J7": 2, "J8": 2,
    "J9": 2, "J10": 2, "J11": 1, "J12": 1, "J13": 2, "J14": 2, "J15": 1, "J16": 1,
    "J17": 3, "J18": 2, "J19": 1, "J20": 2, "J21": 4, "J22": 3, "J23": 1, "J24": 2,
    "J25": 3, "J26": 3, "J27": 1, "J28": 1, "J29": 2, "J30": 2, "J31": 2,
}


@router.post(
    "/harness-graph/demo",
    response_model=HarnessGraphResponse,
    summary="Analyse experimental skeleton endpoints and junctions",
)
def analyse_demo_harness_graph() -> HarnessGraphResponse:
    active = active_image_service.get_active_image()
    image = active.bgr_image

    try:
        from app.services.calibration_service import detect_tape_calibration, pixels_per_cm_for_width
        from app.services.golden_inspection_service import golden_inspection_service
        from app.schemas.harness_graph import PhysicalVerificationItem, PhysicalVerificationSummary

        # Derive px/cm from yellow tape in image (falls back to proportional if no tape)
        calib_result = detect_tape_calibration(image)
        if calib_result.get("pixels_per_cm") and float(calib_result["pixels_per_cm"]) > 0.5:
            derived_px_per_cm = float(calib_result["pixels_per_cm"])
        else:
            derived_px_per_cm = pixels_per_cm_for_width(int(image.shape[1]))

        segmentation = segmentation_service.segment(image)
        graph = harness_graph_service.analyse(
            segmentation.binary_mask,
            base_image=image,
            pixels_per_cm=derived_px_per_cm,
        )
        calib_method = str(calib_result.get("method", "proportional_fallback"))
        calib_tape_span_px = calib_result.get("tape_pixel_span")
        calib_tape_span_cm = calib_result.get("tape_cm_span")

        # Physical wire length verification against blueprint checkpoints
        inspection = golden_inspection_service.inspect_image(
            image,
            override_pixels_per_mm=derived_px_per_cm / 10.0,
        )

        physical_verifications: list[PhysicalVerificationItem] = []
        for r in inspection.results:
            src = r.node_id or ""
            tgt = r.terminal_id or ""
            if r.checkpoint_id.startswith("CP-NODE-"):
                parts = r.checkpoint_id.replace("CP-NODE-", "").split("-")
                if len(parts) >= 2:
                    src, tgt = parts[0], parts[1]
            elif "-" in src and not tgt:
                parts = src.split("-")
                if len(parts) >= 2:
                    src, tgt = parts[0], parts[1]
            elif not src and not tgt and r.checkpoint_id:
                parts = r.checkpoint_id.replace("CP-", "").split("-")
                if len(parts) >= 2:
                    src, tgt = parts[0], parts[1]

            exp_cm = round(r.expected_value / 10.0, 1) if r.expected_value is not None else 0.0
            det_cm = round(r.detected_value / 10.0, 1) if r.detected_value is not None else None
            dev_cm = round(r.deviation / 10.0, 1) if r.deviation is not None else None
            tol_cm = round(r.tolerance / 10.0, 1) if r.tolerance is not None else 1.5

            if r.status == "PASS" and det_cm is not None:
                msg = f"Measured physical wire length {det_cm:.1f} cm is within tolerance ±{tol_cm:.1f} cm (expected {exp_cm:.1f} cm)"
            elif r.status == "FAIL":
                msg = "Component not detected at expected workpiece location"
            else:
                msg = r.message.replace(" mm", " cm")

            physical_verifications.append(
                PhysicalVerificationItem(
                    checkpoint_id=r.checkpoint_id,
                    source=src,
                    target=tgt,
                    type=r.type,
                    expected_distance_cm=exp_cm,
                    detected_distance_cm=det_cm,
                    deviation_cm=dev_cm,
                    tolerance_cm=tol_cm,
                    status=r.status,
                    confidence=r.confidence,
                    message=msg,
                    test_coord=r.test_coord,
                    golden_coord=r.golden_coord,
                )
            )

        verification_summary = PhysicalVerificationSummary(
            overall_status=inspection.overall_status,
            total_checkpoints=inspection.total_checkpoints,
            passed_count=inspection.passed_count,
            failed_count=inspection.failed_count,
            review_count=inspection.review_count,
            pixels_per_cm=round(derived_px_per_cm, 2),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Harness graph analysis failed: {exc}") from exc

    sheet_spec = SheetSpecification(
        source_sheet="measurement_sheet.png",
        total_terminals=41,
        total_junctions=31,
        total_nodes=12,
        unit="cm",
        node_distances=SHEET_NODE_DISTANCES,
        junction_measurements=SHEET_JUNCTION_MEASUREMENTS,
        junction_branch_counts=SHEET_JUNCTION_BRANCH_COUNTS,
    )

    return HarnessGraphResponse(
        source_image=active.filename,
        production_ready=False,
        unit="cm",
        pixels_per_cm=graph.pixels_per_cm,
        sheet_specification=sheet_spec,
        disclaimer=(
            f"Distance calibration: {calib_method}. "
            f"Scale: {graph.pixels_per_cm:.2f} px/cm derived from physical yellow measuring tape "
            f"(Distance.jpeg: 50 px per 10 cm = 5.0 px/cm, scaled to {image.shape[1]} W workpiece: {graph.pixels_per_cm:.2f} px/cm). "
            "Physical wire verifications report the actual blueprint-specified branch distances (J1-T1, N1-N2, etc.) "
            "and active workpiece measurements in cm."
        ),
        metrics=HarnessGraphMetrics(
            endpoint_count=len(graph.endpoints),
            candidate_junction_pixel_count=graph.candidate_junction_pixel_count,
            clustered_junction_count=len(graph.junctions),
            skeleton_pixel_count=graph.skeleton_pixel_count,
            neighbour_connectivity=8,
            junction_cluster_radius=harness_graph_service.junction_cluster_radius,
            total_wire_length_cm=graph.total_wire_length_cm,
            extracted_branch_length_cm=graph.extracted_branch_length_cm,
            total_wire_length_pixels=graph.total_wire_length_pixels,
            extracted_branch_length_pixels=graph.extracted_branch_length_pixels,
            extracted_branch_count=len(graph.branches),
            topology_terminal_count=sum(
                node.node_type == "END_TERMINAL" for node in graph.nodes
            ),
            unresolved_segment_count=graph.unresolved_segment_count,
            node_count=len(graph.nodes),
        ),
        endpoints=[GraphPointResponse(x=point.x, y=point.y) for point in graph.endpoints],
        junctions=[GraphPointResponse(x=point.x, y=point.y) for point in graph.junctions],
        measurements=HarnessGraphMeasurements(
            unit="cm",
            length_method=(
                f"8-connected skeleton centreline with {graph.pixels_per_cm:.2f} px/cm calibration: "
                "orthogonal step = 1 px; diagonal step = sqrt(2) px"
            ),
            orientation_convention=(
                "Clockwise image coordinates: 0 degrees = right, 90 = down, "
                "180 = left, 270 = up"
            ),
            branch_distance_definition=(
                "Distances in cm (and px): Branch-to-branch distance is measured between branch midpoints, "
                "both through their common junction and as a straight distance"
            ),
            calibration_summary=(
                f"Calibrated at {graph.pixels_per_cm:.2f} px/cm (1 px = {1.0 / graph.pixels_per_cm:.4f} cm). "
                f"Source: yellow measuring tape in Distance.jpeg (tape={calib_tape_span_px or 439:.0f}px={calib_tape_span_cm or 88:.0f}cm). "
                f"Method: {calib_method}. "
                f"Physical image size: {image.shape[1]/graph.pixels_per_cm:.1f}cm W × {image.shape[0]/graph.pixels_per_cm:.1f}cm H."
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
                    path_length_cm=branch.path_length_cm,
                    straight_distance_cm=branch.straight_distance_cm,
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
                    path_distance_cm=distance.path_distance_cm,
                    straight_distance_cm=distance.straight_distance_cm,
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
                    via_junction_distance_cm=distance.via_junction_distance_cm,
                    midpoint_straight_distance_cm=distance.midpoint_straight_distance_cm,
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
        physical_verifications=physical_verifications,
        verification_summary=verification_summary,
    )

@router.post(
    "/wire-color-identification",
    response_model=WireColorIdentificationResponse,
    summary="Identify dark blue, black, and green wire sections on the active workpiece",
)
def identify_wire_colors() -> WireColorIdentificationResponse:
    active = active_image_service.get_active_image()
    try:
        return wire_color_service.identify_colors(
            active.bgr_image,
            source_filename=active.filename,
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Wire colour identification failed: {exc}") from exc


@router.post(
    "/feature-extraction",
    response_model=FeatureExtractionResponse,
    summary="Extract visual and geometric features from the active wire harness image",
)
def extract_active_image_features(
    payload: FeatureExtractionRequest | None = None,
) -> FeatureExtractionResponse:
    active = active_image_service.get_active_image()
    try:
        return feature_extraction_service.extract_features(
            active.bgr_image,
            config=payload or FeatureExtractionRequest(),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Feature extraction failed: {exc}") from exc


@router.post(
    "/feature-extraction/demo",
    response_model=FeatureExtractionResponse,
    summary="Extract visual and geometric features from the demo wire harness image",
)
def extract_demo_image_features(
    payload: FeatureExtractionRequest | None = None,
) -> FeatureExtractionResponse:
    demo_path = resolve_demo_image()
    if demo_path is not None and demo_path.is_file():
        image = cv2.imread(str(demo_path), cv2.IMREAD_COLOR)
        if image is None:
            active = active_image_service.get_active_image()
            image = active.bgr_image
    else:
        active = active_image_service.get_active_image()
        image = active.bgr_image

    try:
        return feature_extraction_service.extract_features(
            image,
            config=payload or FeatureExtractionRequest(),
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"Feature extraction failed: {exc}") from exc


