from __future__ import annotations

import heapq
import math
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray
from skimage.morphology import skeletonize

from app.services.harness_segmentation_service import ImageArray


@dataclass(frozen=True, slots=True)
class GraphPoint:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class BranchOrientation:
    branch_id: str
    angle_degrees: float


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    node_type: str
    point: GraphPoint
    branch_count: int
    branch_orientations: list[BranchOrientation]


@dataclass(frozen=True, slots=True)
class GraphBranch:
    branch_id: str
    source_node_id: str
    target_node_id: str
    path_length_pixels: float
    straight_distance_pixels: float
    orientation_degrees: float
    path_length_cm: float = 0.0
    straight_distance_cm: float = 0.0


@dataclass(frozen=True, slots=True)
class JunctionTerminalDistance:
    junction_node_id: str
    terminal_node_id: str
    path_distance_pixels: float
    straight_distance_pixels: float
    path_distance_cm: float = 0.0
    straight_distance_cm: float = 0.0


@dataclass(frozen=True, slots=True)
class BranchPairDistance:
    junction_node_id: str
    first_branch_id: str
    second_branch_id: str
    via_junction_distance_pixels: float
    midpoint_straight_distance_pixels: float
    angular_separation_degrees: float
    via_junction_distance_cm: float = 0.0
    midpoint_straight_distance_cm: float = 0.0


@dataclass(frozen=True, slots=True)
class HarnessGraphResult:
    skeleton_image: ImageArray
    overlay_image: ImageArray
    endpoints: list[GraphPoint]
    junctions: list[GraphPoint]
    candidate_junction_pixel_count: int
    skeleton_pixel_count: int
    total_wire_length_pixels: float
    extracted_branch_length_pixels: float
    unresolved_segment_count: int
    nodes: list[GraphNode]
    branches: list[GraphBranch]
    junction_terminal_distances: list[JunctionTerminalDistance]
    branch_pair_distances: list[BranchPairDistance]
    total_wire_length_cm: float = 0.0
    extracted_branch_length_cm: float = 0.0
    pixels_per_cm: float = 6.70


class HarnessGraphService:
    """Experimental topology and pixel measurement over a binary harness mask.

    Orthogonal skeleton steps have length 1 px and diagonal steps have length
    sqrt(2) px. Results remain feasibility estimates and are not inspection
    decision inputs.
    """

    def __init__(self, *, junction_cluster_radius: int = 10) -> None:
        if junction_cluster_radius < 1:
            raise ValueError("junction_cluster_radius must be at least 1")
        self.junction_cluster_radius = junction_cluster_radius

    def analyse(
        self,
        binary_mask: ImageArray,
        *,
        base_image: ImageArray | None = None,
        pixels_per_cm: float | None = None,
    ) -> HarnessGraphResult:
        if binary_mask.ndim != 2:
            raise ValueError("Expected a single-channel binary mask")
        if binary_mask.size == 0:
            raise ValueError("Binary mask is empty")

        if pixels_per_cm is None or pixels_per_cm <= 0:
            try:
                from app.services.calibration_service import pixels_per_cm_for_width
                w = int(binary_mask.shape[1])
                pixels_per_cm = pixels_per_cm_for_width(w)
            except Exception:
                # Ultimate fallback: proportional to calibration reference
                # Calibration: 459px wide image → 47.70 px/cm
                w = int(binary_mask.shape[1])
                pixels_per_cm = round(47.70 * (w / 459), 4)

        skeleton_bool = skeletonize(binary_mask > 0)
        skeleton = skeleton_bool.astype(np.uint8)
        neighbour_kernel = np.ones((3, 3), dtype=np.uint8)
        neighbour_kernel[1, 1] = 0
        neighbour_count = cv2.filter2D(
            skeleton,
            cv2.CV_16S,
            neighbour_kernel,
            borderType=cv2.BORDER_CONSTANT,
        )
        endpoint_mask = skeleton_bool & (neighbour_count == 1)
        junction_candidate_mask = skeleton_bool & (neighbour_count > 2)

        endpoints = self._points_from_mask(endpoint_mask)
        junctions, junction_regions = self._cluster_junction_candidates(
            junction_candidate_mask,
            skeleton_bool,
        )
        topology = self._measure_topology(
            skeleton_bool,
            endpoint_mask,
            junctions,
            junction_regions,
            pixels_per_cm=pixels_per_cm,
        )
        nodes, branches, terminal_distances, branch_pair_distances, unresolved = topology

        skeleton_image = skeleton * 255
        overlay_image = self._draw_overlay(
            skeleton_image,
            nodes=nodes,
            base_image=base_image,
        )
        total_wire_px = self._skeleton_length(skeleton_bool)
        extracted_branch_px = sum(branch.path_length_pixels for branch in branches)
        return HarnessGraphResult(
            skeleton_image=skeleton_image,
            overlay_image=overlay_image,
            endpoints=endpoints,
            junctions=junctions,
            candidate_junction_pixel_count=int(np.count_nonzero(junction_candidate_mask)),
            skeleton_pixel_count=int(np.count_nonzero(skeleton_bool)),
            total_wire_length_pixels=total_wire_px,
            extracted_branch_length_pixels=extracted_branch_px,
            unresolved_segment_count=unresolved,
            nodes=nodes,
            branches=branches,
            junction_terminal_distances=terminal_distances,
            branch_pair_distances=branch_pair_distances,
            total_wire_length_cm=round(total_wire_px / pixels_per_cm, 2),
            extracted_branch_length_cm=round(extracted_branch_px / pixels_per_cm, 2),
            pixels_per_cm=round(pixels_per_cm, 4),
        )

    @staticmethod
    def _points_from_mask(mask: NDArray[np.bool_]) -> list[GraphPoint]:
        coordinates = np.argwhere(mask)
        return [GraphPoint(x=int(x), y=int(y)) for y, x in coordinates]

    def _cluster_junction_candidates(
        self,
        mask: NDArray[np.bool_],
        skeleton: NDArray[np.bool_],
    ) -> tuple[list[GraphPoint], list[NDArray[np.bool_]]]:
        candidate_image = mask.astype(np.uint8)
        if not np.any(candidate_image):
            return [], []
        diameter = self.junction_cluster_radius * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (diameter, diameter))
        expanded = cv2.dilate(candidate_image, kernel, iterations=1)
        component_count, labels = cv2.connectedComponents(expanded, connectivity=8)

        clusters: list[GraphPoint] = []
        regions: list[NDArray[np.bool_]] = []
        candidate_y, candidate_x = np.where(mask)
        for label in range(1, component_count):
            belongs_to_cluster = labels[candidate_y, candidate_x] == label
            if not np.any(belongs_to_cluster):
                continue
            x_values = candidate_x[belongs_to_cluster]
            y_values = candidate_y[belongs_to_cluster]
            clusters.append(GraphPoint(
                x=int(round(float(np.mean(x_values)))),
                y=int(round(float(np.mean(y_values)))),
            ))
            regions.append(skeleton & (labels == label))
        return clusters, regions

    def _measure_topology(
        self,
        skeleton: NDArray[np.bool_],
        endpoint_mask: NDArray[np.bool_],
        junctions: list[GraphPoint],
        junction_regions: list[NDArray[np.bool_]],
        pixels_per_cm: float = 6.70,
    ) -> tuple[
        list[GraphNode],
        list[GraphBranch],
        list[JunctionTerminalDistance],
        list[BranchPairDistance],
        int,
    ]:
        node_labels = np.zeros(skeleton.shape, dtype=np.int32)
        node_ids: list[str] = []
        node_types: list[str] = []
        node_points: list[GraphPoint] = []

        for index, (point, region) in enumerate(zip(junctions, junction_regions), start=1):
            node_ids.append(f"J{index:03d}")
            node_types.append("JUNCTION")
            node_points.append(point)
            node_labels[region] = index

        terminal_count = 0
        for point in self._points_from_mask(endpoint_mask):
            if node_labels[point.y, point.x] != 0:
                continue
            terminal_count += 1
            node_ids.append(f"T{terminal_count:03d}")
            node_types.append("END_TERMINAL")
            node_points.append(point)
            node_labels[point.y, point.x] = len(node_ids)

        residual = skeleton & (node_labels == 0)
        component_count, component_labels = cv2.connectedComponents(
            residual.astype(np.uint8), connectivity=8
        )
        branches: list[GraphBranch] = []
        unresolved_segment_count = 0
        neighbour_kernel = np.ones((3, 3), dtype=np.uint8)

        for component_label in range(1, component_count):
            component = component_labels == component_label
            expanded = cv2.dilate(component.astype(np.uint8), neighbour_kernel, iterations=1) > 0
            touching_labels = np.unique(node_labels[expanded & (node_labels > 0)])
            if len(touching_labels) != 2:
                unresolved_segment_count += 1
                continue
            source_index, target_index = sorted(int(label) - 1 for label in touching_labels)
            source_point = node_points[source_index]
            target_point = node_points[target_index]
            component_y, component_x = np.where(component)
            path_length = (
                self._skeleton_length(component)
                + self._nearest_distance(source_point, component_x, component_y)
                + self._nearest_distance(target_point, component_x, component_y)
            )
            straight_dist = self._point_distance(source_point, target_point)
            branches.append(GraphBranch(
                branch_id=f"B{len(branches) + 1:03d}",
                source_node_id=node_ids[source_index],
                target_node_id=node_ids[target_index],
                path_length_pixels=path_length,
                straight_distance_pixels=straight_dist,
                orientation_degrees=self._orientation(source_point, target_point),
                path_length_cm=round(path_length / pixels_per_cm, 2),
                straight_distance_cm=round(straight_dist / pixels_per_cm, 2),
            ))

        incident: dict[str, list[GraphBranch]] = {node_id: [] for node_id in node_ids}
        for branch in branches:
            incident[branch.source_node_id].append(branch)
            incident[branch.target_node_id].append(branch)

        point_by_id = dict(zip(node_ids, node_points))
        nodes = [GraphNode(
            node_id=node_id,
            node_type=node_type,
            point=point,
            branch_count=len(incident[node_id]),
            branch_orientations=[BranchOrientation(
                branch_id=branch.branch_id,
                angle_degrees=self._orientation(
                    point,
                    point_by_id[
                        branch.target_node_id
                        if branch.source_node_id == node_id
                        else branch.source_node_id
                    ],
                ),
            ) for branch in incident[node_id]],
        ) for node_id, node_type, point in zip(node_ids, node_types, node_points)]

        return (
            nodes,
            branches,
            self._nearest_terminal_distances(nodes, branches, pixels_per_cm=pixels_per_cm),
            self._branch_pair_distances(nodes, incident, point_by_id, pixels_per_cm=pixels_per_cm),
            unresolved_segment_count,
        )

    @staticmethod
    def _nearest_distance(
        point: GraphPoint,
        x_values: NDArray[np.intp],
        y_values: NDArray[np.intp],
    ) -> float:
        distances = np.hypot(x_values - point.x, y_values - point.y)
        return float(np.min(distances)) if distances.size else 0.0

    @staticmethod
    def _point_distance(first: GraphPoint, second: GraphPoint) -> float:
        return math.hypot(second.x - first.x, second.y - first.y)

    @staticmethod
    def _orientation(first: GraphPoint, second: GraphPoint) -> float:
        return math.degrees(math.atan2(second.y - first.y, second.x - first.x)) % 360.0

    def _nearest_terminal_distances(
        self,
        nodes: list[GraphNode],
        branches: list[GraphBranch],
        pixels_per_cm: float = 6.70,
    ) -> list[JunctionTerminalDistance]:
        node_by_id = {node.node_id: node for node in nodes}
        terminal_ids = {node.node_id for node in nodes if node.node_type == "END_TERMINAL"}
        adjacency: dict[str, list[tuple[str, float]]] = {node.node_id: [] for node in nodes}
        for branch in branches:
            adjacency[branch.source_node_id].append((branch.target_node_id, branch.path_length_pixels))
            adjacency[branch.target_node_id].append((branch.source_node_id, branch.path_length_pixels))

        results: list[JunctionTerminalDistance] = []
        for junction in (node for node in nodes if node.node_type == "JUNCTION"):
            nearest = self._dijkstra_nearest_terminal(junction.node_id, terminal_ids, adjacency)
            if nearest is None:
                continue
            terminal_id, path_distance = nearest
            straight_dist = self._point_distance(
                junction.point, node_by_id[terminal_id].point
            )
            results.append(JunctionTerminalDistance(
                junction_node_id=junction.node_id,
                terminal_node_id=terminal_id,
                path_distance_pixels=path_distance,
                straight_distance_pixels=straight_dist,
                path_distance_cm=round(path_distance / pixels_per_cm, 2),
                straight_distance_cm=round(straight_dist / pixels_per_cm, 2),
            ))
        return results

    @staticmethod
    def _dijkstra_nearest_terminal(
        start_id: str,
        terminal_ids: set[str],
        adjacency: dict[str, list[tuple[str, float]]],
    ) -> tuple[str, float] | None:
        distances = {start_id: 0.0}
        queue: list[tuple[float, str]] = [(0.0, start_id)]
        while queue:
            distance, node_id = heapq.heappop(queue)
            if distance > distances[node_id]:
                continue
            if node_id in terminal_ids:
                return node_id, distance
            for neighbour, edge_length in adjacency[node_id]:
                candidate = distance + edge_length
                if candidate < distances.get(neighbour, math.inf):
                    distances[neighbour] = candidate
                    heapq.heappush(queue, (candidate, neighbour))
        return None

    def _branch_pair_distances(
        self,
        nodes: list[GraphNode],
        incident: dict[str, list[GraphBranch]],
        point_by_id: dict[str, GraphPoint],
        pixels_per_cm: float = 6.70,
    ) -> list[BranchPairDistance]:
        results: list[BranchPairDistance] = []
        for junction in (node for node in nodes if node.node_type == "JUNCTION"):
            junction_branches = incident[junction.node_id]
            for first_index, first in enumerate(junction_branches):
                for second in junction_branches[first_index + 1:]:
                    first_other = first.target_node_id if first.source_node_id == junction.node_id else first.source_node_id
                    second_other = second.target_node_id if second.source_node_id == junction.node_id else second.source_node_id
                    first_midpoint = GraphPoint(
                        x=int(round((junction.point.x + point_by_id[first_other].x) / 2)),
                        y=int(round((junction.point.y + point_by_id[first_other].y) / 2)),
                    )
                    second_midpoint = GraphPoint(
                        x=int(round((junction.point.x + point_by_id[second_other].x) / 2)),
                        y=int(round((junction.point.y + point_by_id[second_other].y) / 2)),
                    )
                    first_angle = self._orientation(junction.point, point_by_id[first_other])
                    second_angle = self._orientation(junction.point, point_by_id[second_other])
                    angle_delta = abs(first_angle - second_angle)
                    via_px = (first.path_length_pixels + second.path_length_pixels) / 2.0
                    straight_px = self._point_distance(first_midpoint, second_midpoint)
                    results.append(BranchPairDistance(
                        junction_node_id=junction.node_id,
                        first_branch_id=first.branch_id,
                        second_branch_id=second.branch_id,
                        via_junction_distance_pixels=via_px,
                        midpoint_straight_distance_pixels=straight_px,
                        angular_separation_degrees=min(angle_delta, 360.0 - angle_delta),
                        via_junction_distance_cm=round(via_px / pixels_per_cm, 2),
                        midpoint_straight_distance_cm=round(straight_px / pixels_per_cm, 2),
                    ))
        return results

    @staticmethod
    def _skeleton_length(mask: NDArray[np.bool_]) -> float:
        horizontal = np.count_nonzero(mask[:, :-1] & mask[:, 1:])
        vertical = np.count_nonzero(mask[:-1, :] & mask[1:, :])
        diagonal_down_right = np.count_nonzero(mask[:-1, :-1] & mask[1:, 1:])
        diagonal_down_left = np.count_nonzero(mask[:-1, 1:] & mask[1:, :-1])
        return float(horizontal + vertical) + float(
            diagonal_down_right + diagonal_down_left
        ) * math.sqrt(2.0)

    @staticmethod
    def _draw_overlay(
        skeleton_image: ImageArray,
        *,
        nodes: list["GraphNode"],
        base_image: ImageArray | None,
    ) -> ImageArray:
        """Draw the skeleton path and all resolved graph nodes on a canvas.

        Every node in the resolved topology list is drawn:
        - END_TERMINAL nodes: white outline + green fill circle (radius 6)
        - JUNCTION nodes:     white outline + blue fill circle (radius 10)

        Node positions come from the topology-resolved node list, so they
        exactly match what is reported in the API response.
        """
        height, width = skeleton_image.shape
        if base_image is None:
            canvas = cv2.cvtColor(skeleton_image, cv2.COLOR_GRAY2BGR)
        else:
            if base_image.ndim != 3 or base_image.shape[:2] != (height, width):
                raise ValueError("Base image dimensions must match the binary mask")
            canvas = base_image.copy()

        # Draw skeleton centreline (amber/orange tint blended over the source image)
        visible_path = cv2.dilate(
            skeleton_image,
            cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)),
            iterations=1,
        )
        path_pixels = visible_path > 0
        path_colour = np.array([255, 170, 0], dtype=np.uint8)
        canvas[path_pixels] = (
            canvas[path_pixels].astype(np.float32) * 0.35 + path_colour * 0.65
        ).astype(np.uint8)

        # Draw terminal nodes first (smaller, so junctions render on top at crossings)
        for node in nodes:
            if node.node_type == "END_TERMINAL":
                cv2.circle(canvas, (node.point.x, node.point.y), 7, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(canvas, (node.point.x, node.point.y), 6, (0, 190, 70), -1, cv2.LINE_AA)
                cv2.circle(canvas, (node.point.x, node.point.y), 3, (255, 255, 255), -1, cv2.LINE_AA)

        # Draw junction nodes on top (larger, clearly distinguishable)
        for node in nodes:
            if node.node_type == "JUNCTION":
                cv2.circle(canvas, (node.point.x, node.point.y), 11, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(canvas, (node.point.x, node.point.y), 9, (0, 0, 230), -1, cv2.LINE_AA)
                cv2.circle(canvas, (node.point.x, node.point.y), 4, (255, 255, 255), -1, cv2.LINE_AA)

        return canvas
