from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import cv2

from app.models import Checkpoint, ProductModel
from app.schemas.inspection import MockInspectionResponse
from app.services.harness_graph_service import (
    GraphBranch,
    GraphPoint,
    HarnessGraphResult,
    HarnessGraphService,
)
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray
from app.services.mock_inspection_service import MockInspectionService


@dataclass(frozen=True, slots=True)
class InspectionReportResult:
    report_id: str
    generated_at: datetime
    inspection: MockInspectionResponse
    graph: HarnessGraphResult
    annotated_image: ImageArray


class ReportingService:
    """Builds an in-memory development report without altering its source image."""

    def __init__(self) -> None:
        self.segmentation_service = HarnessSegmentationService()
        self.graph_service = HarnessGraphService()
        self.inspection_service = MockInspectionService()

    def generate(
        self,
        model: ProductModel,
        checkpoints: list[Checkpoint],
        image: ImageArray,
    ) -> InspectionReportResult:
        inspection = self.inspection_service.evaluate(model, checkpoints)
        segmentation = self.segmentation_service.segment(image)
        graph = self.graph_service.analyse(segmentation.binary_mask, base_image=image)
        generated_at = datetime.now(UTC)
        return InspectionReportResult(
            report_id=f"RPT-{generated_at:%Y%m%d-%H%M%S}",
            generated_at=generated_at,
            inspection=inspection,
            graph=graph,
            annotated_image=self._annotate_measurements(graph),
        )

    @staticmethod
    def _annotate_measurements(graph: HarnessGraphResult) -> ImageArray:
        canvas = graph.overlay_image.copy()
        height, width = canvas.shape[:2]

        pixels_per_cm = 9.16
        try:
            from app.services.golden_reference_service import golden_reference_service
            ppm = golden_reference_service.get_configuration().get("calibration", {}).get("pixels_per_mm", 0.916)
            if ppm and ppm > 0:
                pixels_per_cm = round(float(ppm) * 10.0, 4)
        except Exception:
            pass

        total_wire_length_cm = graph.total_wire_length_pixels / pixels_per_cm

        banner = canvas.copy()
        cv2.rectangle(banner, (12, 12), (width - 12, 108), (48, 29, 8), -1)
        cv2.addWeighted(banner, 0.88, canvas, 0.12, 0, canvas)
        cv2.putText(
            canvas,
            "TOTAL WIRE CENTRELINE",
            (28, 43),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (205, 225, 238),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            f"{total_wire_length_cm:,.1f} cm",
            (28, 82),
            cv2.FONT_HERSHEY_DUPLEX,
            1.08,
            (70, 220, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            "8-CONNECTED WEIGHTED SKELETON / CALIBRATED (cm)",
            (260, 82),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.37,
            (188, 205, 216),
            1,
            cv2.LINE_AA,
        )

        node_points = {node.node_id: node.point for node in graph.nodes}
        labelled_branches = sorted(
            graph.branches,
            key=lambda branch: branch.path_length_pixels,
            reverse=True,
        )[:10]
        occupied_labels: list[tuple[int, int, int, int]] = []
        for branch in labelled_branches:
            ReportingService._draw_branch_label(
                canvas,
                branch,
                node_points,
                occupied_labels,
                pixels_per_cm,
            )

        cv2.rectangle(canvas, (12, height - 43), (width - 12, height - 12), (48, 29, 8), -1)
        cv2.putText(
            canvas,
            "CALIBRATED METRIC MEASUREMENT (cm)",
            (24, height - 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (220, 229, 235),
            1,
            cv2.LINE_AA,
        )
        return canvas

    @staticmethod
    def _draw_branch_label(
        canvas: ImageArray,
        branch: GraphBranch,
        node_points: dict[str, GraphPoint],
        occupied_labels: list[tuple[int, int, int, int]],
        pixels_per_cm: float = 9.16,
    ) -> None:
        source = node_points[branch.source_node_id]
        target = node_points[branch.target_node_id]
        x = int(round((source.x + target.x) / 2))
        y = int(round((source.y + target.y) / 2))
        branch_cm = branch.path_length_pixels / pixels_per_cm
        label = f"{branch.branch_id} {branch_cm:.1f}cm"
        (text_width, text_height), _ = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.34, 1
        )
        x = max(4, min(x - text_width // 2, canvas.shape[1] - text_width - 8))
        y = max(122, min(y, canvas.shape[0] - 52))
        for y_offset in (0, -22, 22, -44, 44, -66, 66):
            candidate_y = max(122, min(y + y_offset, canvas.shape[0] - 52))
            candidate = (
                x - 3,
                candidate_y - text_height - 4,
                x + text_width + 3,
                candidate_y + 4,
            )
            if not any(
                candidate[0] <= existing[2]
                and candidate[2] >= existing[0]
                and candidate[1] <= existing[3]
                and candidate[3] >= existing[1]
                for existing in occupied_labels
            ):
                y = candidate_y
                occupied_labels.append(candidate)
                break
        cv2.rectangle(
            canvas,
            (x - 3, y - text_height - 4),
            (x + text_width + 3, y + 4),
            (48, 29, 8),
            -1,
        )
        cv2.putText(
            canvas,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.34,
            (70, 220, 255),
            1,
            cv2.LINE_AA,
        )
