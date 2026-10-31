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


def _encode_png_base64(image: ImageArray) -> str:
    """Encode an OpenCV BGR or grayscale image to a PNG data URL."""
    encoded, buf = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("Failed to encode image to PNG")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


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
    compact_path: list[list[int]]


class FeatureExtractionService:
    """Comprehensive Feature Extraction Module for AI Wire Harness Inspection.

    Extracts:
    1. Edge extraction (Canny edges, harness boundary gating, background edge suppression).
    2. Contour extraction (external/internal contours, hierarchy, main harness contour, geometric shape properties).
    3. Skeleton & Centerline extraction (1-px skeleton, ordered paths, crossing vs. joint discrimination).
    4. Geometric feature extraction (angles, distances, curvature, bend angles, straightness).
    5. Wire & branch features (ordered coordinates, tangent vectors, lengths in pixels).
    6. Terminal and Joint candidate support (shape descriptors and ROIs for Part Identification).
    7. Multi-layer visualizations (Original, Edges, Contours, Skeleton, Nodes, Combined Overlay).
    """

    def __init__(
        self,
        *,
        segmentation_service: HarnessSegmentationService | None = None,
        graph_service: HarnessGraphService | None = None,
    ) -> None:
        self.segmentation_service = segmentation_service or HarnessSegmentationService()
        self.graph_service = graph_service or HarnessGraphService()

    def extract_features(
        self,
        image: ImageArray,
        *,
        mask: ImageArray | None = None,
        config: FeatureExtractionRequest | None = None,
    ) -> FeatureExtractionResponse:
        """Run the end-to-end feature extraction pipeline on an input image."""
        started_time = time.perf_counter()
        warnings: list[str] = []
        errors: list[str] = []

        self._validate_input_image(image)
        h, w = image.shape[:2]
        channels = image.shape[2] if image.ndim == 3 else 1
        dimensions = ImageDimensions(width=w, height=h, channels=channels)

        cfg = config or FeatureExtractionRequest()

        # Step A: Segmentation Mask (reuse existing HarnessSegmentationService if not supplied)
        seg_result: HarnessSegmentationResult | None = None
        if mask is None:
            try:
                seg_result = self.segmentation_service.segment(image)
                binary_mask = seg_result.binary_mask
            except Exception as exc:
                errors.append(f"Segmentation failed: {exc}")
                binary_mask = np.zeros((h, w), dtype=np.uint8)
        else:
            if mask.shape[:2] != (h, w):
                raise ValueError("Provided binary mask dimensions do not match the input image")
            binary_mask = (mask > 0).astype(np.uint8) * 255

        # Step B: Edge Extraction (Canny + Mask-Gated Background Filtering)
        edge_data = self._extract_edges(
            image,
            binary_mask,
            low_thresh=cfg.canny_low_threshold,
            high_thresh=cfg.canny_high_threshold,
        )

        # Step C: Contour Extraction & Hierarchy
        contour_data = self._extract_contours(
            binary_mask,
            min_area=cfg.min_contour_area,
        )

        # Step D: Skeleton, Centerline Paths & Topology (reusing HarnessGraphService primitives)
        skeleton_bool = skeletonize(binary_mask > 0)
        skeleton_img = (skeleton_bool.astype(np.uint8)) * 255
        graph_result = self.graph_service.analyse(binary_mask, base_image=image)

        ordered_branches = self._trace_branch_paths(
            skeleton_bool,
            graph_result.nodes,
            graph_result.branches,
            curvature_window=cfg.curvature_window,
        )

        # Step E: Crossing vs. Electrical Joint Discrimination
        junction_candidates = self._classify_junctions(
            graph_result.nodes,
            ordered_branches,
        )

        # Step F: Endpoint Candidates & Tangent Angles
        endpoint_candidates = self._extract_endpoints_with_tangents(
            graph_result.nodes,
            ordered_branches,
        )

        # Step G: Candidate Regions for Part Identification Module
        candidate_rois = self._extract_candidate_rois_for_part_id(
            image,
            binary_mask,
            endpoint_candidates,
            junction_candidates,
        )

        # Step H: Geometric Features Aggregation
        geometric_features = self._calculate_geometric_features(
            endpoint_candidates,
            junction_candidates,
            ordered_branches,
        )

        # Always clearly identify uncalibrated values
        warnings.append(
            "Every dimensional measurement (lengths, areas, perimeters) is reported in UNCALIBRATED PIXELS. "
            "Downstream length measurement must apply optical scale (px/cm or px/mm) calibration."
        )

        # Step I: Multi-Layer Visualizations
        visualizations: FeatureVisualizations | None = None
        if cfg.generate_visualizations:
            visualizations = self._generate_visualizations(
                image,
                binary_mask,
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

        return FeatureExtractionResponse(
            image_dimensions=dimensions,
            edge_statistics=edge_data.stats,
            contour_information=contour_data.contours_info,
            skeleton_features=skeleton_features,
            candidate_regions_for_part_id=candidate_rois,
            geometric_features=geometric_features,
            visualizations=visualizations,
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
        # RETR_CCOMP retrieves a two-level hierarchy: external boundaries and holes/internal contours
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

                # In cv2.RETR_CCOMP: hierarchy[i][3] == -1 indicates an external contour
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
                        hierarchy_level=2 if is_internal else 1,
                    )
                )

        main_contour_info: MainHarnessContour | None = None
        if main_contour_idx is not None:
            mc = contours[main_contour_idx]
            mc_area = float(cv2.contourArea(mc))
            mc_perim = float(cv2.arcLength(mc, True))
            bx, by, bw, bh = cv2.boundingRect(mc)
            mc_hull = cv2.convexHull(mc)
            mc_hull_area = float(cv2.contourArea(mc_hull))
            mc_solidity = round(mc_area / mc_hull_area, 3) if mc_hull_area > 0 else 0.0
            mc_extent = round(mc_area / float(bw * bh), 3) if (bw * bh) > 0 else 0.0
            moments = cv2.moments(mc)
            cx = round(moments["m10"] / moments["m00"], 1) if moments["m00"] != 0 else float(bx + bw / 2)
            cy = round(moments["m01"] / moments["m00"], 1) if moments["m00"] != 0 else float(by + bh / 2)

            main_contour_info = MainHarnessContour(
                area=round(mc_area, 2),
                perimeter=round(mc_perim, 2),
                bounding_box=BoundingBox(x=bx, y=by, width=bw, height=bh),
                aspect_ratio=round(float(bw) / float(bh), 3) if bh > 0 else 0.0,
                solidity=mc_solidity,
                extent=mc_extent,
                center_x=cx,
                center_y=cy,
            )

        info = ContourInformation(
            total_contours=len(descriptors),
            external_contours_count=external_count,
            internal_contours_count=internal_count,
            main_harness_contour=main_contour_info,
            significant_contours=descriptors[:50],  # Keep top 50 in payload to prevent bloating
        )

        return RawContourFeatures(
            contours_info=info,
            raw_contours=contours,
            hierarchy=hierarchy,
            main_contour_index=main_contour_idx,
        )

    # =========================================================================
    # 3. Skeleton Tracing, Curvature & Ordered Paths
    # =========================================================================
    def _trace_branch_paths(
        self,
        skeleton: NDArray[np.bool_],
        nodes: list[GraphNode],
        branches: list[GraphBranch],
        curvature_window: int = 7,
    ) -> list[OrderedBranchPath]:
        """Trace continuous ordered pixel paths for each graph branch and calculate geometric curvature."""
        node_map = {n.node_id: n for n in nodes}
        results: list[OrderedBranchPath] = []

        # Find connected components of skeleton between nodes
        node_mask = np.zeros(skeleton.shape, dtype=bool)
        for n in nodes:
            # Mask out node vicinity so branches disconnect
            cv2.circle(node_mask.view(np.uint8), (n.point.x, n.point.y), 3, 1, -1)

        for branch in branches:
            src = node_map.get(branch.source_node_id)
            tgt = node_map.get(branch.target_node_id)
            if not src or not tgt:
                continue

            # Trace straight-line seeded path through skeleton
            pts = self._find_path_points_between_nodes(skeleton, src.point, tgt.point)
            if len(pts) < 2:
                pts = [(src.point.x, src.point.y), (tgt.point.x, tgt.point.y)]

            # Compute path length
            path_len = 0.0
            for i in range(len(pts) - 1):
                dx = abs(pts[i + 1][0] - pts[i][0])
                dy = abs(pts[i + 1][1] - pts[i][1])
                path_len += math.sqrt(2.0) if (dx > 0 and dy > 0) else 1.0

            straight_dist = math.hypot(tgt.point.x - src.point.x, tgt.point.y - src.point.y)
            straightness = round(straight_dist / max(1.0, path_len), 4)
            straightness = min(1.0, straightness)

            # Curvature and bend angles
            mean_curv, max_bend = self._calculate_path_curvature(pts, window=curvature_window)

            # Compact polyline (approximate with Douglas-Peucker)
            compact = self._simplify_path(pts, epsilon=1.8)

            results.append(
                OrderedBranchPath(
                    branch_id=branch.branch_id,
                    source_node=branch.source_node_id,
                    target_node=branch.target_node_id,
                    points=pts,
                    path_length_px=path_len,
                    straight_dist_px=straight_dist,
                    straightness_ratio=straightness,
                    orientation_deg=branch.orientation_degrees,
                    mean_curvature=mean_curv,
                    max_bend_angle_deg=max_bend,
                    compact_path=compact,
                )
            )

        return results

    @staticmethod
    def _find_path_points_between_nodes(
        skeleton: NDArray[np.bool_],
        src: GraphPoint,
        tgt: GraphPoint,
    ) -> list[tuple[int, int]]:
        """Find ordered 8-connected path between two points along the skeleton using BFS/A*."""
        h, w = skeleton.shape
        start = (src.x, src.y)
        goal = (tgt.x, tgt.y)

        # Fast search within bounding box with padding
        pad = 20
        min_x = max(0, min(src.x, tgt.x) - pad)
        max_x = min(w - 1, max(src.x, tgt.x) + pad)
        min_y = max(0, min(src.y, tgt.y) - pad)
        max_y = min(h - 1, max(src.y, tgt.y) + pad)

        visited = set()
        queue = [(start, [start])]
        visited.add(start)

        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

        # If goal is reached or closest point when direct connection is slightly gapped
        best_path = [start, goal]
        min_dist_to_goal = math.hypot(start[0] - goal[0], start[1] - goal[1])

        iterations = 0
        max_iters = 8000

        while queue and iterations < max_iters:
            iterations += 1
            curr, path = queue.pop(0)
            cx, cy = curr

            dist = math.hypot(cx - goal[0], cy - goal[1])
            if dist <= 2.5:
                path.append(goal)
                return path

            if dist < min_dist_to_goal:
                min_dist_to_goal = dist
                best_path = path

            # Sort neighbours by Euclidean distance to goal (greedy A* behavior)
            nbrs = []
            for dx, dy in directions:
                nx, ny = cx + dx, cy + dy
                if min_x <= nx <= max_x and min_y <= ny <= max_y:
                    if (nx, ny) not in visited:
                        # Allow path to traverse skeleton pixels, or reach near the goal
                        if skeleton[ny, nx] or (math.hypot(nx - goal[0], ny - goal[1]) <= 2.0):
                            nbrs.append((nx, ny))

            nbrs.sort(key=lambda p: math.hypot(p[0] - goal[0], p[1] - goal[1]))
            for nbr in nbrs:
                visited.add(nbr)
                queue.append((nbr, path + [nbr]))

        return best_path + [goal]

    @staticmethod
    def _calculate_path_curvature(
        points: list[tuple[int, int]],
        window: int = 7,
    ) -> tuple[float, float]:
        """Compute mean discrete curvature and maximum bend angle along an ordered path."""
        if len(points) < window * 2 + 1:
            return 0.0, 0.0

        bend_angles: list[float] = []
        curvatures: list[float] = []

        w = max(2, window // 2)
        for i in range(w, len(points) - w):
            p_prev = points[i - w]
            p_curr = points[i]
            p_next = points[i + w]

            v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
            v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])

            len1 = math.hypot(v1[0], v1[1])
            len2 = math.hypot(v2[0], v2[1])

            if len1 == 0 or len2 == 0:
                continue

            dot = (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)
            dot = max(-1.0, min(1.0, dot))
            angle_rad = math.acos(dot)
            angle_deg = math.degrees(angle_rad)

            bend_angles.append(angle_deg)
            # Local curvature = angle / arc length
            arc_len = (len1 + len2) / 2.0
            if arc_len > 0:
                curvatures.append(angle_rad / arc_len)

        mean_curv = float(np.mean(curvatures)) if curvatures else 0.0
        max_bend = float(np.max(bend_angles)) if bend_angles else 0.0
        return mean_curv, max_bend

    @staticmethod
    def _simplify_path(points: list[tuple[int, int]], epsilon: float = 1.8) -> list[list[int]]:
        """Compress ordered pixel path using Douglas-Peucker approximation for compact representation."""
        if len(points) <= 2:
            return [[int(x), int(y)] for x, y in points]

        pts_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))
        simplified = cv2.approxPolyDP(pts_array, epsilon, False)
        return [[int(pt[0][0]), int(pt[0][1])] for pt in simplified]

    # =========================================================================
    # 4. Crossing vs. True Joint Discrimination
    # =========================================================================
    @staticmethod
    def _classify_junctions(
        nodes: list[GraphNode],
        branches: list[OrderedBranchPath],
    ) -> list[JunctionCandidate]:
        """Classify junction candidates and determine if they are simple visual wire crossings or spliced joints."""
        junctions: list[JunctionCandidate] = []

        for node in nodes:
            if node.node_type != "JUNCTION":
                continue

            branch_angles = [float(bo.angle_degrees) for bo in node.branch_orientations]
            is_simple_crossing = False

            # A 4-way intersection (or degree 4) where opposing branches are ~180° apart indicates a visual crossing
            if len(branch_angles) == 4:
                sorted_angles = sorted(branch_angles)
                # Check pairs: (0, 2) and (1, 3)
                diff1 = abs((sorted_angles[2] - sorted_angles[0]) - 180.0)
                diff2 = abs((sorted_angles[3] - sorted_angles[1]) - 180.0)
                if diff1 <= 30.0 and diff2 <= 30.0:
                    is_simple_crossing = True

            junctions.append(
                JunctionCandidate(
                    id=node.node_id,
                    x=node.point.x,
                    y=node.point.y,
                    branch_count=node.branch_count,
                    is_simple_crossing=is_simple_crossing,
                    branch_angles_deg=[round(a, 2) for a in branch_angles],
                )
            )

        return junctions

    # =========================================================================
    # 5. Endpoint Tangent Extraction
    # =========================================================================
    @staticmethod
    def _extract_endpoints_with_tangents(
        nodes: list[GraphNode],
        branches: list[OrderedBranchPath],
    ) -> list[EndpointCandidate]:
        """Extract endpoint candidates and calculate local tangent orientation along the incident branch."""
        endpoints: list[EndpointCandidate] = []

        for node in nodes:
            if node.node_type != "END_TERMINAL":
                continue

            # Find incident branch to determine outward tangent direction
            tangent_angle = 0.0
            for b in branches:
                if b.source_node == node.node_id and len(b.points) >= 4:
                    # Vector from node into the branch, then flip to point outward
                    p1 = b.points[0]
                    p2 = b.points[min(5, len(b.points) - 1)]
                    tangent_angle = math.degrees(math.atan2(p1[1] - p2[1], p1[0] - p2[0])) % 360.0
                    break
                elif b.target_node == node.node_id and len(b.points) >= 4:
                    p1 = b.points[-1]
                    p2 = b.points[max(0, len(b.points) - 6)]
                    tangent_angle = math.degrees(math.atan2(p1[1] - p2[1], p1[0] - p2[0])) % 360.0
                    break

            endpoints.append(
                EndpointCandidate(
                    id=node.node_id,
                    x=node.point.x,
                    y=node.point.y,
                    tangent_angle_deg=round(tangent_angle, 2),
                    connection_degree=node.branch_count,
                )
            )

        return endpoints

    # =========================================================================
    # 6. Terminal and Joint Candidate ROIs for Part Identification
    # =========================================================================
    @staticmethod
    def _extract_candidate_rois_for_part_id(
        image: ImageArray,
        mask: ImageArray,
        endpoints: list[EndpointCandidate],
        junctions: list[JunctionCandidate],
        roi_half_size: int = 24,
    ) -> list[CandidateRegionForPartId]:
        """Generate bounding regions and local shape descriptors for the Part Identification module.

        Important: An endpoint is only a candidate terminal location. It must NOT be claimed as a
        detected terminal solely from a skeleton endpoint until Part Identification verifies it.
        """
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
        """Calculate pairwise feature point distances, straightness distribution and max bend angles."""
        straightnesses = [b.straightness_ratio for b in branches]
        mean_straightness = float(np.mean(straightnesses)) if straightnesses else 1.0
        max_bends = [b.max_bend_angle_deg for b in branches]
        max_bend_deg = float(np.max(max_bends)) if max_bends else 0.0

        # Pairwise distances between nearest feature points
        pairwise: list[PairwiseDistance] = []
        all_points: list[tuple[str, int, int]] = []
        for ep in endpoints:
            all_points.append((ep.id, ep.x, ep.y))
        for jc in junctions:
            all_points.append((jc.id, jc.x, jc.y))

        for i in range(len(all_points)):
            for j in range(i + 1, min(len(all_points), i + 6)):  # Nearest neighborhood pairs
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
            pairwise_feature_distances=pairwise[:40],
        )

    # =========================================================================
    # 8. Multi-Layer Visualizations
    # =========================================================================
    def _generate_visualizations(
        self,
        image: ImageArray,
        mask: ImageArray,
        edge_data: RawEdgeFeatures,
        contour_data: RawContourFeatures,
        skeleton_img: ImageArray,
        endpoints: list[EndpointCandidate],
        junctions: list[JunctionCandidate],
        branches: list[OrderedBranchPath],
        candidate_rois: list[CandidateRegionForPartId],
    ) -> FeatureVisualizations:
        """Create 6 distinct, professionally styled visualization layers as PNG data URLs."""
        h, w = image.shape[:2]

        # 1. Preprocessed original
        vis_preprocessed = _encode_png_base64(image)

        # 2. Edge Map (Cyan boundary edges on dark background, dim red filtered noise)
        edge_canvas = np.zeros((h, w, 3), dtype=np.uint8)
        edge_canvas[edge_data.filtered_edges > 0] = (30, 30, 160)  # dim red background noise
        edge_canvas[edge_data.boundary_edges > 0] = (255, 230, 0)   # bright cyan boundary edges
        vis_edge = _encode_png_base64(edge_canvas)

        # 3. Contour Visualization
        contour_canvas = image.copy()
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
        vis_contour = _encode_png_base64(contour_canvas)

        # 4. Skeleton Visualization (amber centerline on neutral board)
        skel_canvas = np.full((h, w, 3), 32, dtype=np.uint8)
        dilated_skel = cv2.dilate(
            skeleton_img,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        skel_canvas[dilated_skel > 0] = (0, 175, 255)  # amber centerline
        vis_skeleton = _encode_png_base64(skel_canvas)

        # 5. Keypoints & Junction Visualization (endpoints green, true joints red, crossings orange)
        kp_canvas = image.copy()
        # Draw candidate ROI bounding boxes
        for roi in candidate_rois:
            b = roi.bounding_box
            box_col = (0, 200, 0) if roi.candidate_type == "TERMINAL_CANDIDATE" else (0, 0, 230)
            cv2.rectangle(kp_canvas, (b.x, b.y), (b.x + b.width, b.y + b.height), box_col, 1, cv2.LINE_AA)

        # Draw Endpoints
        for ep in endpoints:
            cv2.circle(kp_canvas, (ep.x, ep.y), 7, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(kp_canvas, (ep.x, ep.y), 5, (0, 200, 0), -1, cv2.LINE_AA)
            cv2.putText(
                kp_canvas,
                ep.id,
                (ep.x + 8, ep.y - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 240, 0),
                1,
                cv2.LINE_AA,
            )

        # Draw Junctions & Crossings
        for jc in junctions:
            j_col = (0, 140, 255) if jc.is_simple_crossing else (0, 0, 230)
            cv2.circle(kp_canvas, (jc.x, jc.y), 9, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(kp_canvas, (jc.x, jc.y), 7, j_col, -1, cv2.LINE_AA)
            tag = f"{jc.id}{' (X)' if jc.is_simple_crossing else ''}"
            cv2.putText(
                kp_canvas,
                tag,
                (jc.x + 10, jc.y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                j_col,
                1,
                cv2.LINE_AA,
            )
        vis_keypoints = _encode_png_base64(kp_canvas)

        # 6. Combined Feature Overlay
        overlay = image.copy()
        # Overlay skeleton
        overlay[dilated_skel > 0] = (
            overlay[dilated_skel > 0].astype(np.float32) * 0.3 + np.array([0, 185, 255]) * 0.7
        ).astype(np.uint8)

        # Overlay main contour
        if contour_data.main_contour_index is not None:
            mc = contour_data.raw_contours[contour_data.main_contour_index]
            cv2.drawContours(overlay, [mc], -1, (255, 255, 0), 2, cv2.LINE_AA)

        # Overlay keypoints
        for ep in endpoints:
            cv2.circle(overlay, (ep.x, ep.y), 6, (0, 220, 0), -1, cv2.LINE_AA)
        for jc in junctions:
            col = (0, 140, 255) if jc.is_simple_crossing else (0, 0, 230)
            cv2.circle(overlay, (jc.x, jc.y), 8, col, -1, cv2.LINE_AA)

        # Header overlay bar
        bar_h = max(38, int(h * 0.055))
        bar = overlay.copy()
        cv2.rectangle(bar, (0, 0), (w, bar_h), (20, 20, 20), -1)
        cv2.addWeighted(bar, 0.75, overlay, 0.25, 0, overlay)
        cv2.putText(
            overlay,
            f"FEATURE EXTRACTION OVERLAY: {len(branches)} Branches | {len(endpoints)} Terminal Candidates | {len(junctions)} Junctions",
            (14, bar_h - 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (240, 240, 240),
            1,
            cv2.LINE_AA,
        )
        vis_combined = _encode_png_base64(overlay)

        return FeatureVisualizations(
            original_preprocessed=vis_preprocessed,
            edge_map=vis_edge,
            contour_visualization=vis_contour,
            skeleton_visualization=vis_skeleton,
            keypoint_junction_visualization=vis_keypoints,
            combined_overlay=vis_combined,
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
