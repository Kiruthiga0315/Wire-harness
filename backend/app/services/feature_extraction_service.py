from __future__ import annotations

import base64
import math
import time
from dataclasses import dataclass
from typing import Any, Mapping

import cv2
import numpy as np
from numpy.typing import NDArray
from skimage.morphology import skeletonize

from app.schemas.feature_extraction import (
    BoundingBox,
    BranchFeature,
    CandidateRegionForPartId,
    ContourDescriptor,
    ContourInformation,
    EdgeStatistics,
    EndpointCandidate,
    FeatureExtractionRequest,
    FeatureExtractionResponse,
    FeatureVisualizations,
    GeometricFeatures,
    ImageDimensions,
    JunctionCandidate,
    MainHarnessContour,
    PairwiseDistance,
    QualityControlSummary,
    SkeletonFeatures,
)
from app.services.harness_graph_service import (
    GraphBranch,
    GraphNode,
    GraphPoint,
    HarnessGraphResult,
    HarnessGraphService,
)
from app.services.harness_segmentation_service import (
    HarnessSegmentationResult,
    HarnessSegmentationService,
    ImageArray,
)
from app.services.image_preprocessing_service import (
    ImagePreprocessingService,
    image_preprocessing_service,
)


def _encode_image_base64(image: ImageArray, is_mask: bool = False) -> str:
    """Encode an OpenCV image to base64.

    Uses PNG for 1-bit binary masks to preserve exact pixel values,
    and high-quality JPEG (85) for color diagnostic visualizations to maintain
    crisp visual inspection quality while keeping JSON payloads compact (< 1.5MB).
    """
    if is_mask or image.ndim == 2:
        encoded, buf = cv2.imencode(".png", image)
        mime = "image/png"
    else:
        encoded, buf = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        mime = "image/jpeg"

    if not encoded:
        raise RuntimeError("Failed to encode image to base64")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


@dataclass(slots=True)
class RawEdgeFeatures:
    raw_edges: ImageArray
    boundary_edges: ImageArray
    filtered_edges: ImageArray
    stats: EdgeStatistics


@dataclass(slots=True)
class RawContourFeatures:
    contours_info: ContourInformation
    raw_contours: list[NDArray[np.int32]]
    hierarchy: NDArray[np.int32] | None
    main_contour_index: int | None


@dataclass(slots=True)
class OrderedBranchPath:
    branch_id: str
    source_node: str
    target_node: str
    points: list[tuple[int, int]]
    path_length_px: float
    straight_dist_px: float
    straightness_ratio: float
    orientation_deg: float
    mean_curvature: float
    max_bend_angle_deg: float
    estimated_width_px: float
    compact_path: list[list[int]]


class FeatureExtractionService:
    """Universal Feature Extraction Module for AI Wire Harness Inspection.

    Extracts:
    1. Automatic non-destructive image preprocessing and quality gating.
    2. Edge extraction (Canny edges, harness boundary gating, background edge suppression).
    3. Contour extraction (external/internal contours, hierarchy, main harness contour, geometric shape properties).
    4. Skeleton & Centerline extraction (1-px skeleton, ordered paths, crossing vs. joint discrimination).
    5. Wire width estimation using Euclidean distance transform along branches.
    6. Geometric feature extraction (angles, distances, curvature, bend angles, straightness).
    7. Wire & branch features (ordered coordinates, tangent vectors, lengths in pixels).
    8. Terminal and Joint candidate support (shape descriptors and ROIs for Part Identification).
    9. 10 Diagnostic Engineering View Visualizations.
    10. Quality Control summary with PASS / REVIEW / REJECT statuses and explanations.
    """

    def __init__(
        self,
        *,
        segmentation_service: HarnessSegmentationService | None = None,
        graph_service: HarnessGraphService | None = None,
        preprocessing_service: ImagePreprocessingService | None = None,
    ) -> None:
        self.segmentation_service = segmentation_service or HarnessSegmentationService()
        self.graph_service = graph_service or HarnessGraphService()
        self.preprocessing_service = preprocessing_service or image_preprocessing_service

    def extract_features(
        self,
        image: ImageArray,
        *,
        mask: ImageArray | None = None,
        config: FeatureExtractionRequest | None = None,
    ) -> FeatureExtractionResponse:
        """Run the universal end-to-end feature extraction pipeline on an input image."""
        started_time = time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []
        review_reasons: list[str] = []

        self._validate_input_image(image)
        cfg = config or FeatureExtractionRequest()

        # Step 1: Automatic Preprocessing & Quality Assessment
        prep_result = self.preprocessing_service.preprocess(image)
        preprocessed_img = prep_result.preprocessed_image
        h, w = preprocessed_img.shape[:2]
        channels = preprocessed_img.shape[2] if preprocessed_img.ndim == 3 else 1
        dimensions = ImageDimensions(width=w, height=h, channels=channels)

        if prep_result.quality_metrics.quality_notes:
            warnings.extend(prep_result.quality_metrics.quality_notes)
        if prep_result.quality_metrics.quality_status == "REJECT":
            review_reasons.extend(prep_result.quality_metrics.quality_notes)
        elif prep_result.quality_metrics.quality_status == "REVIEW":
            review_reasons.extend(prep_result.quality_metrics.quality_notes)

        # Step 2: Harness Segmentation
        seg_result: HarnessSegmentationResult | None = None
        if mask is None:
            try:
                seg_result = self.segmentation_service.segment(preprocessed_img)
                binary_mask = seg_result.binary_mask
            except Exception as exc:
                errors.append(f"Segmentation failed: {exc}")
                binary_mask = np.zeros((h, w), dtype=np.uint8)
        else:
            if mask.shape[:2] != (h, w):
                # Resize provided mask to match preprocessed dimensions if rotated
                mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            binary_mask = (mask > 0).astype(np.uint8) * 255

        # Check mask occupancy
        occupied_ratio = float(cv2.countNonZero(binary_mask)) / float(max(1, h * w))
        if occupied_ratio < 0.005:
            errors.append("No wire harness structures detected in segmentation mask.")
            review_reasons.append("Segmentation mask contains < 0.5% harness pixels")

        # Step 3: Edge Extraction (Canny + Mask-Gated Background Filtering)
        edge_data = self._extract_edges(
            preprocessed_img,
            binary_mask,
            low_thresh=cfg.canny_low_threshold,
            high_thresh=cfg.canny_high_threshold,
        )

        # Step 4: Contour Extraction & Hierarchy
        contour_data = self._extract_contours(
            binary_mask,
            min_area=cfg.min_contour_area,
        )

        # Step 5: Skeleton, Centerline Paths & Topology
        skeleton_bool = skeletonize(binary_mask > 0)
        skeleton_img = (skeleton_bool.astype(np.uint8)) * 255
        graph_result = self.graph_service.analyse(binary_mask, base_image=preprocessed_img)

        # Distance transform for wire width estimation
        dist_transform = cv2.distanceTransform(binary_mask, cv2.DIST_L2, 5)

        ordered_branches = self._trace_branch_paths(
            skeleton_bool,
            graph_result.nodes,
            graph_result.branches,
            dist_transform=dist_transform,
            curvature_window=cfg.curvature_window,
        )

        # Step 6: Crossing vs. Electrical Joint Discrimination
        junction_candidates = self._classify_junctions(
            graph_result.nodes,
            ordered_branches,
        )

        uncertain_junctions = [j for j in junction_candidates if j.is_uncertain]
        if uncertain_junctions:
            review_reasons.append(
                f"{len(uncertain_junctions)} wire junction(s) exhibit complex/ambiguous branching requiring operator review"
            )

        # Step 7: Endpoint Candidates & Tangent Angles
        endpoint_candidates = self._extract_endpoints_with_tangents(
            graph_result.nodes,
            ordered_branches,
        )

        # Step 8: Candidate Regions for Part Identification Module
        candidate_rois = self._extract_candidate_rois_for_part_id(
            preprocessed_img,
            binary_mask,
            endpoint_candidates,
            junction_candidates,
        )

        # Step 9: Geometric Features Aggregation
        geometric_features = self._calculate_geometric_features(
            endpoint_candidates,
            junction_candidates,
            ordered_branches,
        )

        # Quality Control Status Evaluation
        seg_conf = seg_result.segmentation_confidence if seg_result else 0.85
        if prep_result.quality_metrics.quality_status == "REJECT" or occupied_ratio < 0.005:
            qc_status = "REJECT"
        elif prep_result.quality_metrics.quality_status == "REVIEW" or len(uncertain_junctions) > 0 or seg_conf < 0.70:
            qc_status = "REVIEW"
        else:
            qc_status = "PASS"

        qc_summary = QualityControlSummary(
            quality_status=qc_status,
            segmentation_confidence=round(seg_conf, 2),
            image_quality_status=prep_result.quality_metrics.quality_status,
            detected_components_count=contour_data.contours_info.total_contours,
            endpoints_count=len(endpoint_candidates),
            junction_candidates_count=len(junction_candidates),
            branches_count=len(ordered_branches),
            uncertain_junctions_count=len(uncertain_junctions),
            extraction_warnings=warnings,
            reasons_for_review_or_reject=review_reasons,
        )

        # Always clearly identify uncalibrated values
        warnings.append(
            "Every dimensional measurement (lengths, areas, perimeters, wire widths) is reported in UNCALIBRATED PIXELS. "
            "Downstream length measurement must apply optical scale (px/cm or px/mm) calibration."
        )

        # Step 10: 10 Diagnostic Engineering Visualizations
        visualizations: FeatureVisualizations | None = None
        if cfg.generate_visualizations:
            visualizations = self._generate_visualizations(
                image,
                preprocessed_img,
                binary_mask,
                seg_result.isolated_harness_image if seg_result and seg_result.isolated_harness_image is not None else None,
                edge_data,
                contour_data,
                skeleton_img,
                endpoint_candidates,
                junction_candidates,
                ordered_branches,
                candidate_rois,
            )

        branch_schemas = [
            BranchFeature(
                branch_id=b.branch_id,
                start_node=b.source_node,
                end_node=b.target_node,
                path_length_pixels=round(b.path_length_px, 2),
                straight_distance_pixels=round(b.straight_dist_px, 2),
                straightness_ratio=round(b.straightness_ratio, 4),
                orientation_deg=round(b.orientation_deg, 2),
                mean_curvature=round(b.mean_curvature, 5),
                max_bend_angle_deg=round(b.max_bend_angle_deg, 2),
                estimated_width_pixels=round(b.estimated_width_px, 2),
                compact_path=b.compact_path,
            )
            for b in ordered_branches
        ]

        skeleton_features = SkeletonFeatures(
            total_wire_length_pixels=round(graph_result.total_wire_length_pixels, 2),
            uncalibrated=True,
            skeleton_pixel_count=int(np.count_nonzero(skeleton_bool)),
            endpoint_candidates=endpoint_candidates,
            junction_candidates=junction_candidates,
            branches=branch_schemas,
        )

        elapsed_ms = (time.perf_counter() - started_time) * 1000.0
        model_status_str = seg_result.model_status if seg_result else "HYBRID_CV_PIPELINE"

        return FeatureExtractionResponse(
            image_dimensions=dimensions,
            edge_statistics=edge_data.stats,
            contour_information=contour_data.contours_info,
            skeleton_features=skeleton_features,
            candidate_regions_for_part_id=candidate_rois,
            geometric_features=geometric_features,
            visualizations=visualizations,
            quality_control=qc_summary,
            model_status=model_status_str,
            processing_time_ms=round(elapsed_ms, 2),
            warnings=warnings,
            errors=errors,
        )

    # =========================================================================
    # 1. Edge Extraction
    # =========================================================================
    def _extract_edges(
        self,
        image: ImageArray,
        mask: ImageArray,
        low_thresh: int = 50,
        high_thresh: int = 150,
    ) -> RawEdgeFeatures:
        """Run Canny edge detection, gate by harness mask to remove background clutter."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)
        raw_edges = cv2.Canny(blurred, low_thresh, high_thresh)

        # Dilate mask slightly so boundary transitions are preserved inside the gate
        gate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        gated_zone = cv2.dilate(mask, gate_kernel, iterations=1)

        # Wire and harness boundary edges are within the gated zone
        boundary_edges = cv2.bitwise_and(raw_edges, raw_edges, mask=gated_zone)

        # Filter out tiny disconnected speckles in boundary edges
        comp_count, labels, stats, _ = cv2.connectedComponentsWithStats(boundary_edges, connectivity=8)
        cleaned_boundary = np.zeros_like(boundary_edges)
        for label in range(1, comp_count):
            if stats[label, cv2.CC_STAT_AREA] >= 6:
                cleaned_boundary[labels == label] = 255

        # Edges outside the gate are background clutter/noise
        filtered_edges = cv2.bitwise_and(raw_edges, raw_edges, mask=cv2.bitwise_not(gated_zone))

        total_pixels = float(image.shape[0] * image.shape[1])
        total_edge_px = int(np.count_nonzero(raw_edges))
        boundary_edge_px = int(np.count_nonzero(cleaned_boundary))
        filtered_bg_px = int(np.count_nonzero(filtered_edges))
        edge_density = round(total_edge_px / total_pixels, 5) if total_pixels > 0 else 0.0

        stats_obj = EdgeStatistics(
            total_edge_pixels=total_edge_px,
            edge_density=edge_density,
            boundary_edge_pixels=boundary_edge_px,
            filtered_background_edges=filtered_bg_px,
        )

        return RawEdgeFeatures(
            raw_edges=raw_edges,
            boundary_edges=cleaned_boundary,
            filtered_edges=filtered_edges,
            stats=stats_obj,
        )

    # =========================================================================
    # 2. Contour Extraction
    # =========================================================================
    def _extract_contours(
        self,
        mask: ImageArray,
        min_area: float = 30.0,
    ) -> RawContourFeatures:
        """Extract external and internal contours, calculate shape descriptors, identify main harness."""
        contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)

        descriptors: list[ContourDescriptor] = []
        external_count = 0
        internal_count = 0
        main_contour_idx: int | None = None
        max_area = 0.0

        if hierarchy is not None and len(contours) > 0:
            h_data = hierarchy[0]
            for idx, cnt in enumerate(contours):
                area = float(cv2.contourArea(cnt))
                if area < min_area:
                    continue

                perimeter = float(cv2.arcLength(cnt, True))
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect_ratio = round(float(bw) / float(bh), 3) if bh > 0 else 0.0
                bbox_area = float(bw * bh)
                extent = round(area / bbox_area, 3) if bbox_area > 0 else 0.0

                hull = cv2.convexHull(cnt)
                hull_area = float(cv2.contourArea(hull))
                solidity = round(area / hull_area, 3) if hull_area > 0 else 0.0

                parent_idx = int(h_data[idx][3])
                is_internal = parent_idx != -1
                if is_internal:
                    internal_count += 1
                else:
                    external_count += 1
                    if area > max_area:
                        max_area = area
                        main_contour_idx = idx

                descriptors.append(
                    ContourDescriptor(
                        contour_id=idx,
                        area=round(area, 2),
                        perimeter=round(perimeter, 2),
                        bounding_box=BoundingBox(x=bx, y=by, width=bw, height=bh),
                        aspect_ratio=aspect_ratio,
                        solidity=solidity,
                        extent=extent,
                        is_internal=is_internal,
                        hierarchy_level=1 if is_internal else 0,
                    )
                )

        main_harness_desc: MainHarnessContour | None = None
        if main_contour_idx is not None:
            mc = contours[main_contour_idx]
            bx, by, bw, bh = cv2.boundingRect(mc)
            moments = cv2.moments(mc)
            cx = float(moments["m10"] / moments["m00"]) if moments["m00"] != 0 else float(bx + bw / 2)
            cy = float(moments["m01"] / moments["m00"]) if moments["m00"] != 0 else float(by + bh / 2)
            hull = cv2.convexHull(mc)
            hull_area = float(cv2.contourArea(hull))
            sol = round(max_area / hull_area, 3) if hull_area > 0 else 0.0
            main_harness_desc = MainHarnessContour(
                area=round(max_area, 2),
                perimeter=round(float(cv2.arcLength(mc, True)), 2),
                bounding_box=BoundingBox(x=bx, y=by, width=bw, height=bh),
                aspect_ratio=round(float(bw) / float(bh), 3) if bh > 0 else 0.0,
                solidity=sol,
                extent=round(max_area / float(bw * bh), 3) if bw * bh > 0 else 0.0,
                center_x=round(cx, 1),
                center_y=round(cy, 1),
            )

        info = ContourInformation(
            total_contours=len(descriptors),
            external_contours_count=external_count,
            internal_contours_count=internal_count,
            main_harness_contour=main_harness_desc,
            significant_contours=descriptors[:100],
        )

        return RawContourFeatures(
            contours_info=info,
            raw_contours=contours,
            hierarchy=hierarchy,
            main_contour_index=main_contour_idx,
        )

    # =========================================================================
    # 3. Skeleton Branch Tracing & Curvature
    # =========================================================================
    def _trace_branch_paths(
        self,
        skeleton: NDArray[np.bool_],
        nodes: list[GraphNode] | Mapping[str, GraphNode],
        branches: list[GraphBranch] | Mapping[str, GraphBranch],
        dist_transform: ImageArray | None = None,
        curvature_window: int = 7,
    ) -> list[OrderedBranchPath]:
        """Order points along each branch path and compute curvature, bend angle, straightness, and wire width."""
        results: list[OrderedBranchPath] = []
        node_dict: dict[str, GraphNode] = (
            {n.node_id: n for n in nodes} if isinstance(nodes, list) else dict(nodes)
        )
        branch_list: list[GraphBranch] = (
            list(branches) if isinstance(branches, list) else list(branches.values())
        )
        node_lookup = {nid: (n.point.x, n.point.y) for nid, n in node_dict.items()}

        for branch in branch_list:
            b_id = branch.branch_id
            src_pt = node_lookup.get(branch.source_node_id, (0, 0))
            tgt_pt = node_lookup.get(branch.target_node_id, (0, 0))
            raw_pts = getattr(branch, "points", None)
            if raw_pts and len(raw_pts) >= 2:
                pts = [(p.x, p.y) if hasattr(p, "x") else (p[0], p[1]) for p in raw_pts]
            else:
                pts = [src_pt, tgt_pt]

            ordered = self._order_branch_points(pts)

            # Euclidean straight line distance
            dx = float(ordered[-1][0] - ordered[0][0])
            dy = float(ordered[-1][1] - ordered[0][1])
            straight_dist = math.hypot(dx, dy)

            # Along-wire path length
            path_len = getattr(branch, "path_length_pixels", 0.0)
            if path_len <= 0.0:
                path_len = 0.0
                for i in range(1, len(ordered)):
                    path_len += math.hypot(ordered[i][0] - ordered[i - 1][0], ordered[i][1] - ordered[i - 1][1])

            straightness = (straight_dist / path_len) if path_len > 0 else 1.0
            straightness = min(1.0, max(0.0, straightness))

            # Orientation angle in degrees [0, 360)
            angle_rad = math.atan2(dy, dx)
            angle_deg = (math.degrees(angle_rad) + 360.0) % 360.0

            # Local curvature and maximum bend angle along the path
            mean_curv, max_bend = self._calculate_path_curvature(ordered, window=curvature_window)

            # Wire width estimation via distance transform
            mean_width = 0.0
            if dist_transform is not None and len(ordered) > 0:
                h_dt, w_dt = dist_transform.shape[:2]
                widths = []
                for px, py in ordered:
                    if 0 <= px < w_dt and 0 <= py < h_dt:
                        widths.append(float(dist_transform[py, px]) * 2.0)
                if widths:
                    mean_width = float(np.median(widths))

            # Compact subsampled path for lightweight transmission
            step = max(1, len(ordered) // 30)
            compact = [[p[0], p[1]] for p in ordered[::step]]
            if compact[-1] != [ordered[-1][0], ordered[-1][1]]:
                compact.append([ordered[-1][0], ordered[-1][1]])

            results.append(
                OrderedBranchPath(
                    branch_id=b_id,
                    source_node=branch.source_node_id,
                    target_node=branch.target_node_id,
                    points=ordered,
                    path_length_px=path_len,
                    straight_dist_px=straight_dist,
                    straightness_ratio=straightness,
                    orientation_deg=angle_deg,
                    mean_curvature=mean_curv,
                    max_bend_angle_deg=max_bend,
                    estimated_width_px=mean_width,
                    compact_path=compact,
                )
            )

        return results

    @staticmethod
    def _order_branch_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Order an unordered set of 8-connected skeleton points into a continuous traversal."""
        if len(points) <= 2:
            return points

        pts_set = set(points)
        start = min(points, key=lambda p: (p[0], p[1]))

        ordered: list[tuple[int, int]] = [start]
        pts_set.remove(start)

        current = start
        while pts_set:
            cx, cy = current
            best_next = None
            best_dist = 999999.0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    candidate = (cx + dx, cy + dy)
                    if candidate in pts_set:
                        d = math.hypot(dx, dy)
                        if d < best_dist:
                            best_dist = d
                            best_next = candidate
            if best_next is not None:
                ordered.append(best_next)
                pts_set.remove(best_next)
                current = best_next
            else:
                next_nearest = min(pts_set, key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
                ordered.append(next_nearest)
                pts_set.remove(next_nearest)
                current = next_nearest

        return ordered

    @staticmethod
    def _calculate_path_curvature(
        points: list[tuple[int, int]],
        window: int = 7,
    ) -> tuple[float, float]:
        """Compute mean curvature and maximum bend angle using tangent angle changes."""
        if len(points) < window * 2:
            return 0.0, 0.0

        half_w = max(1, window // 2)
        angles: list[float] = []

        for i in range(half_w, len(points) - half_w):
            p_prev = points[i - half_w]
            p_next = points[i + half_w]
            dx = p_next[0] - p_prev[0]
            dy = p_next[1] - p_prev[1]
            angles.append(math.atan2(dy, dx))

        if len(angles) < 2:
            return 0.0, 0.0

        angle_diffs: list[float] = []
        for i in range(1, len(angles)):
            diff = abs(angles[i] - angles[i - 1])
            if diff > math.pi:
                diff = 2 * math.pi - diff
            angle_diffs.append(diff)

        mean_curv = float(np.mean(angle_diffs)) if angle_diffs else 0.0
        max_bend_deg = math.degrees(float(np.max(angle_diffs))) if angle_diffs else 0.0

        return mean_curv, max_bend_deg

    # =========================================================================
    # 4. Junction Classification: Crossing vs. Joint
    # =========================================================================
    @staticmethod
    def _classify_junctions(
        nodes: list[GraphNode] | Mapping[str, GraphNode],
        branches: list[OrderedBranchPath],
    ) -> list[JunctionCandidate]:
        """Discriminate between visual wire overlap crossings vs spliced joints.

        A junction with degree 4 having two opposing pairs of branch vectors (~180 deg)
        is a simple physical pass-through crossing.
        Non-orthogonal or degree-3/5+ junctions are true joint candidates or uncertain splices.
        """
        junctions: list[JunctionCandidate] = []
        node_list: list[GraphNode] = list(nodes) if isinstance(nodes, list) else list(nodes.values())

        for node in node_list:
            if getattr(node, "node_type", "").upper() != "JUNCTION":
                continue

            n_id = node.node_id
            angles = [bo.angle_degrees for bo in getattr(node, "branch_orientations", [])]
            degree = getattr(node, "branch_count", len(angles))

            is_crossing = False
            is_uncertain = False

            if degree == 4 and len(angles) == 4:
                sorted_ang = sorted(angles)
                diff1 = abs((sorted_ang[2] - sorted_ang[0]) - 180.0)
                diff2 = abs((sorted_ang[3] - sorted_ang[1]) - 180.0)
                if diff1 < 35.0 and diff2 < 35.0:
                    is_crossing = True
                else:
                    is_uncertain = True
            elif degree >= 5:
                is_uncertain = True

            junctions.append(
                JunctionCandidate(
                    id=n_id,
                    x=node.point.x,
                    y=node.point.y,
                    branch_count=degree,
                    is_simple_crossing=is_crossing,
                    is_uncertain=is_uncertain,
                    branch_angles_deg=angles,
                )
            )

        return junctions

    # =========================================================================
    # 5. Endpoint Extraction & Tangent Angles
    # =========================================================================
    @staticmethod
    def _extract_endpoints_with_tangents(
        nodes: list[GraphNode] | Mapping[str, GraphNode],
        branches: list[OrderedBranchPath],
    ) -> list[EndpointCandidate]:
        """Extract terminal endpoints with outbound tangent angles."""
        endpoints: list[EndpointCandidate] = []
        node_list: list[GraphNode] = list(nodes) if isinstance(nodes, list) else list(nodes.values())

        for node in node_list:
            ntype = getattr(node, "node_type", "").upper()
            if ntype not in ("END_TERMINAL", "TERMINAL"):
                continue

            n_id = node.node_id
            orientations = getattr(node, "branch_orientations", [])
            tangent_deg = orientations[0].angle_degrees if orientations else 0.0

            endpoints.append(
                EndpointCandidate(
                    id=n_id,
                    x=node.point.x,
                    y=node.point.y,
                    tangent_angle_deg=round(tangent_deg, 2),
                    connection_degree=getattr(node, "branch_count", 1),
                )
            )

        return endpoints

    # =========================================================================
    # 6. Candidate Regions for Part Identification Module
    # =========================================================================
    @staticmethod
    def _extract_candidate_rois_for_part_id(
        image: ImageArray,
        mask: ImageArray,
        endpoints: list[EndpointCandidate],
        junctions: list[JunctionCandidate],
        roi_half_size: int = 18,
    ) -> list[CandidateRegionForPartId]:
        """Generate bounding regions for terminal pin connectors and spliced joints."""
        h, w = image.shape[:2]
        candidates: list[CandidateRegionForPartId] = []

        # 1. Terminal Candidates around endpoints
        for ep in endpoints:
            x1 = max(0, ep.x - roi_half_size)
            y1 = max(0, ep.y - roi_half_size)
            x2 = min(w, ep.x + roi_half_size)
            y2 = min(h, ep.y + roi_half_size)
            bw = x2 - x1
            bh = y2 - y1

            local_mask = mask[y1:y2, x1:x2]
            local_area = float(cv2.countNonZero(local_mask))
            local_aspect = round(float(bw) / float(bh), 3) if bh > 0 else 1.0

            candidates.append(
                CandidateRegionForPartId(
                    candidate_type="TERMINAL_CANDIDATE",
                    associated_node_id=ep.id,
                    bounding_box=BoundingBox(x=x1, y=y1, width=bw, height=bh),
                    local_area=local_area,
                    local_aspect_ratio=local_aspect,
                    note="Candidate endpoint location; awaiting Part Identification confirmation.",
                )
            )

        # 2. Joint Candidates around junctions
        for jc in junctions:
            size = roi_half_size + 6
            x1 = max(0, jc.x - size)
            y1 = max(0, jc.y - size)
            x2 = min(w, jc.x + size)
            y2 = min(h, jc.y + size)
            bw = x2 - x1
            bh = y2 - y1

            local_mask = mask[y1:y2, x1:x2]
            local_area = float(cv2.countNonZero(local_mask))
            local_aspect = round(float(bw) / float(bh), 3) if bh > 0 else 1.0

            candidates.append(
                CandidateRegionForPartId(
                    candidate_type="JOINT_CANDIDATE",
                    associated_node_id=jc.id,
                    bounding_box=BoundingBox(x=x1, y=y1, width=bw, height=bh),
                    local_area=local_area,
                    local_aspect_ratio=local_aspect,
                    note="Candidate junction node; awaiting Part Identification connector/joint confirmation.",
                )
            )

        return candidates

    # =========================================================================
    # 7. Geometric Features Aggregation
    # =========================================================================
    @staticmethod
    def _calculate_geometric_features(
        endpoints: list[EndpointCandidate],
        junctions: list[JunctionCandidate],
        branches: list[OrderedBranchPath],
    ) -> GeometricFeatures:
        """Calculate pairwise feature point distances, straightness distribution, max bend angles, and wire widths."""
        straightnesses = [b.straightness_ratio for b in branches]
        mean_straightness = float(np.mean(straightnesses)) if straightnesses else 1.0
        max_bends = [b.max_bend_angle_deg for b in branches]
        max_bend_deg = float(np.max(max_bends)) if max_bends else 0.0

        widths = [b.estimated_width_px for b in branches if b.estimated_width_px > 0]
        mean_width = float(np.mean(widths)) if widths else 0.0

        # Pairwise distances between nearest feature points
        pairwise: list[PairwiseDistance] = []
        all_points: list[tuple[str, int, int]] = []
        for ep in endpoints:
            all_points.append((ep.id, ep.x, ep.y))
        for jc in junctions:
            all_points.append((jc.id, jc.x, jc.y))

        for i in range(len(all_points)):
            for j in range(i + 1, min(len(all_points), i + 6)):
                id1, x1, y1 = all_points[i]
                id2, x2, y2 = all_points[j]
                dist = math.hypot(x2 - x1, y2 - y1)
                pairwise.append(
                    PairwiseDistance(
                        from_node=id1,
                        to_node=id2,
                        distance_pixels=round(dist, 2),
                    )
                )

        return GeometricFeatures(
            mean_branch_straightness=round(mean_straightness, 4),
            max_bend_angle_deg=round(max_bend_deg, 2),
            total_detected_joints=len(junctions),
            total_detected_terminals=len(endpoints),
            mean_estimated_wire_width_pixels=round(mean_width, 2),
            pairwise_feature_distances=pairwise[:40],
        )

    # =========================================================================
    # 8. 10 Diagnostic Engineering View Visualizations
    # =========================================================================
    def _generate_visualizations(
        self,
        raw_original: ImageArray,
        preprocessed_img: ImageArray,
        mask: ImageArray,
        isolated_harness_img: ImageArray | None,
        edge_data: RawEdgeFeatures,
        contour_data: RawContourFeatures,
        skeleton_img: ImageArray,
        endpoints: list[EndpointCandidate],
        junctions: list[JunctionCandidate],
        branches: list[OrderedBranchPath],
        candidate_rois: list[CandidateRegionForPartId],
    ) -> FeatureVisualizations:
        """Create 10 distinct, diagnostic Engineering View visualization layers."""
        h, w = preprocessed_img.shape[:2]

        # 1. Original Image (Raw upload)
        vis_original = _encode_image_base64(raw_original)

        # 2. Preprocessed Image (Denoised, illumination normalized)
        vis_preprocessed = _encode_image_base64(preprocessed_img)

        # 3. Segmentation Overlay (Semi-transparent emerald mask over preprocessed workpiece)
        seg_overlay = preprocessed_img.copy()
        mask_bool = mask > 0
        if np.any(mask_bool):
            green_tint = np.array([30, 200, 30], dtype=np.float32)
            seg_overlay[mask_bool] = (
                seg_overlay[mask_bool].astype(np.float32) * 0.45 + green_tint * 0.55
            ).astype(np.uint8)
        vis_seg_overlay = _encode_image_base64(seg_overlay)

        # 4. Binary Harness Mask (Exact 1-bit binary representation: wires white 255, background 0)
        vis_binary_mask = _encode_image_base64(mask, is_mask=True)

        # 5. Isolated Harness on White Background (No board markings, text, or lines)
        if isolated_harness_img is not None:
            vis_isolated = _encode_image_base64(isolated_harness_img)
        else:
            isolated_canvas = np.full_like(preprocessed_img, 255)
            if np.any(mask_bool):
                isolated_canvas[mask_bool] = preprocessed_img[mask_bool]
            vis_isolated = _encode_image_base64(isolated_canvas)

        # 6. Contour Visualization (External boundaries green, internal voids yellow, bounding boxes)
        contour_canvas = preprocessed_img.copy()
        for desc in contour_data.contours_info.significant_contours:
            cnt = contour_data.raw_contours[desc.contour_id]
            color = (0, 230, 255) if desc.is_internal else (0, 220, 0)
            cv2.drawContours(contour_canvas, [cnt], -1, color, 2, cv2.LINE_AA)

        if contour_data.contours_info.main_harness_contour:
            mb = contour_data.contours_info.main_harness_contour.bounding_box
            cv2.rectangle(
                contour_canvas,
                (mb.x, mb.y),
                (mb.x + mb.width, mb.y + mb.height),
                (255, 80, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                contour_canvas,
                f"MAIN HARNESS ({mb.width}x{mb.height} px)",
                (mb.x + 8, max(24, mb.y - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 80, 0),
                2,
                cv2.LINE_AA,
            )
        vis_contour = _encode_image_base64(contour_canvas)

        # 7. Skeleton Visualization (1-pixel centerline highlighted on clean dark surface)
        skel_canvas = np.full((h, w, 3), 28, dtype=np.uint8)
        dilated_skel = cv2.dilate(
            skeleton_img,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        skel_canvas[dilated_skel > 0] = (0, 185, 255)  # Amber centerline
        vis_skeleton = _encode_image_base64(skel_canvas)

        # 8. Endpoints and Junction Visualization (Green endpoints, Red joints, Orange crossings)
        kp_canvas = preprocessed_img.copy()
        for roi in candidate_rois:
            b = roi.bounding_box
            box_col = (0, 200, 0) if roi.candidate_type == "TERMINAL_CANDIDATE" else (0, 0, 230)
            cv2.rectangle(kp_canvas, (b.x, b.y), (b.x + b.width, b.y + b.height), box_col, 1, cv2.LINE_AA)

        for ep in endpoints:
            cv2.circle(kp_canvas, (ep.x, ep.y), 7, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(kp_canvas, (ep.x, ep.y), 5, (0, 200, 0), -1, cv2.LINE_AA)
            cv2.putText(kp_canvas, ep.id, (ep.x + 8, ep.y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 240, 0), 1, cv2.LINE_AA)

        for jc in junctions:
            j_col = (0, 140, 255) if jc.is_simple_crossing else (0, 0, 230)
            cv2.circle(kp_canvas, (jc.x, jc.y), 9, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(kp_canvas, (jc.x, jc.y), 7, j_col, -1, cv2.LINE_AA)
            tag = f"{jc.id}{' (X)' if jc.is_simple_crossing else ''}"
            cv2.putText(kp_canvas, tag, (jc.x + 10, jc.y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, j_col, 1, cv2.LINE_AA)
        vis_keypoints = _encode_image_base64(kp_canvas)

        # 9. Branch Paths Visualization (Distinct pseudo-colors per wire branch)
        branch_canvas = preprocessed_img.copy()
        palette = [
            (255, 99, 71),   # Tomato
            (30, 144, 255),  # Dodger blue
            (50, 205, 50),   # Lime green
            (255, 215, 0),   # Gold
            (147, 112, 219), # Medium purple
            (0, 206, 209),   # Dark turquoise
            (255, 105, 180), # Hot pink
            (255, 140, 0),   # Dark orange
        ]
        for idx, b in enumerate(branches):
            col = palette[idx % len(palette)]
            if len(b.points) >= 2:
                pts_arr = np.array(b.points, dtype=np.int32).reshape((-1, 1, 2))
                cv2.polylines(branch_canvas, [pts_arr], False, col, 3, cv2.LINE_AA)
                # Draw branch label at midpoint
                mid_pt = b.points[len(b.points) // 2]
                cv2.putText(
                    branch_canvas,
                    b.branch_id,
                    (mid_pt[0] + 5, mid_pt[1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.40,
                    col,
                    1,
                    cv2.LINE_AA,
                )
        vis_branches = _encode_image_base64(branch_canvas)

        # 10. Feature Extraction Results (Rich Composite Overlay)
        composite = preprocessed_img.copy()
        composite[dilated_skel > 0] = (
            composite[dilated_skel > 0].astype(np.float32) * 0.3 + np.array([0, 185, 255]) * 0.7
        ).astype(np.uint8)

        if contour_data.main_contour_index is not None:
            mc = contour_data.raw_contours[contour_data.main_contour_index]
            cv2.drawContours(composite, [mc], -1, (255, 255, 0), 2, cv2.LINE_AA)

        for ep in endpoints:
            cv2.circle(composite, (ep.x, ep.y), 6, (0, 220, 0), -1, cv2.LINE_AA)
        for jc in junctions:
            col = (0, 140, 255) if jc.is_simple_crossing else (0, 0, 230)
            cv2.circle(composite, (jc.x, jc.y), 8, col, -1, cv2.LINE_AA)

        # Top diagnostic status bar
        bar_h = min(h, max(20, int(h * 0.055)))
        bar = composite.copy()
        cv2.rectangle(bar, (0, 0), (w, bar_h), (20, 20, 20), -1)
        cv2.addWeighted(bar, 0.75, composite, 0.25, 0, composite)
        cv2.putText(
            composite,
            f"HARNESS DIAGNOSTICS: {len(branches)} Branches | {len(endpoints)} Terminals | {len(junctions)} Junctions",
            (14, bar_h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        vis_composite = _encode_image_base64(composite)

        # Edge canvas for backward compatibility
        edge_canvas = np.zeros((h, w, 3), dtype=np.uint8)
        edge_canvas[edge_data.filtered_edges > 0] = (30, 30, 160)
        edge_canvas[edge_data.boundary_edges > 0] = (255, 230, 0)
        vis_edge = _encode_image_base64(edge_canvas)

        return FeatureVisualizations(
            original_image=vis_original,
            preprocessed_image=vis_preprocessed,
            segmentation_overlay=vis_seg_overlay,
            binary_mask=vis_binary_mask,
            isolated_harness=vis_isolated,
            contour_visualization=vis_contour,
            skeleton_visualization=vis_skeleton,
            endpoints_junctions_visualization=vis_keypoints,
            branch_paths_visualization=vis_branches,
            feature_extraction_results=vis_composite,
            # Backward compatibility aliases
            original_preprocessed=vis_preprocessed,
            edge_map=vis_edge,
            keypoint_junction_visualization=vis_keypoints,
            combined_overlay=vis_composite,
        )

    @staticmethod
    def _validate_input_image(image: ImageArray) -> None:
        """Validate that the image is a valid 8-bit array with reasonable dimensions."""
        if not isinstance(image, np.ndarray):
            raise ValueError("Input image must be a numpy ndarray")
        if image.dtype != np.uint8:
            raise ValueError("Input image must use 8-bit unsigned integer channels (np.uint8)")
        if image.ndim not in (2, 3):
            raise ValueError("Input image must have 2 dimensions (grayscale) or 3 dimensions (BGR)")
        if image.shape[0] < 16 or image.shape[1] < 16:
            raise ValueError(f"Image dimensions {image.shape[:2]} are too small for feature extraction")
