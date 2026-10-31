from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Mapping

import cv2
import numpy as np

from app.services.harness_graph_service import HarnessGraphService
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray
from app.services.feature_extraction_service import FeatureExtractionService

InspectionStatus = Literal["PASS", "FAIL", "REVIEW_REQUIRED", "NOT_EVALUATED"]
SUPPORTED_MODEL_SUFFIXES = {".pt", ".onnx", ".engine", ".weights", ".pth", ".pb", ".tflite"}
DEFAULT_VARIANT = "DEMO-HARNESS-001"
ENGINE_VERSION = "0.2.0"


class InspectionInputError(ValueError):
    """Raised when an uploaded image or engine configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ModelStatus:
    state: Literal["MISSING", "UNSUPPORTED", "READY"]
    available: bool
    model_version: str
    model_format: str | None
    device: str
    message: str


@dataclass(frozen=True, slots=True)
class ObjectDetection:
    label: str
    confidence: float
    bounding_box: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class RuleResult:
    rule_id: str
    rule_name: str
    status: InspectionStatus
    actual_value: str | None
    expected_value: str | None
    message: str


@dataclass(frozen=True, slots=True)
class MeasurementValue:
    measurement_id: str
    name: str
    value: float
    unit: str
    method: str


@dataclass(frozen=True, slots=True)
class BranchMeasurement:
    branch_id: str
    source_node_id: str
    target_node_id: str
    path_length_pixels: float
    straight_distance_pixels: float
    orientation_degrees: float


@dataclass(frozen=True, slots=True)
class JunctionMeasurement:
    node_id: str
    x: int
    y: int
    branch_count: int
    branch_orientations: tuple[tuple[str, float], ...]


@dataclass(frozen=True, slots=True)
class JunctionTerminalMeasurement:
    junction_node_id: str
    terminal_node_id: str
    path_distance_pixels: float
    straight_distance_pixels: float


@dataclass(frozen=True, slots=True)
class BranchPairMeasurement:
    junction_node_id: str
    first_branch_id: str
    second_branch_id: str
    via_junction_distance_pixels: float
    midpoint_straight_distance_pixels: float
    angular_separation_degrees: float


@dataclass(frozen=True, slots=True)
class InspectionResult:
    inspection_id: str
    timestamp: datetime
    overall_status: InspectionStatus
    image_width: int
    image_height: int
    annotated_image: ImageArray
    detected_components: dict[str, int]
    detections: list[ObjectDetection]
    rule_results: list[RuleResult]
    model_status: ModelStatus
    selected_variant: str
    warnings: list[str]
    errors: list[str]
    measurements: list[MeasurementValue]
    branches: list[BranchMeasurement]
    junctions: list[JunctionMeasurement]
    junction_terminal_distances: list[JunctionTerminalMeasurement]
    branch_pair_distances: list[BranchPairMeasurement]
    processing_time_ms: float
    configuration: dict[str, Any] = field(default_factory=dict)
    features: Any | None = None

    def to_summary_dict(self) -> dict[str, Any]:
        data = {
            "inspection_id": self.inspection_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status,
            "image": {"width": self.image_width, "height": self.image_height},
            "selected_variant": self.selected_variant,
            "model": {
                "state": self.model_status.state,
                "available": self.model_status.available,
                "version": self.model_status.model_version,
                "format": self.model_status.model_format,
                "device": self.model_status.device,
                "message": self.model_status.message,
            },
            "detected_components": self.detected_components,
            "detections": [
                {
                    "label": item.label,
                    "confidence": item.confidence,
                    "bounding_box": list(item.bounding_box),
                }
                for item in self.detections
            ],
            "rule_results": [
                {
                    "rule_id": item.rule_id,
                    "rule_name": item.rule_name,
                    "status": item.status,
                    "actual_value": item.actual_value,
                    "expected_value": item.expected_value,
                    "message": item.message,
                }
                for item in self.rule_results
            ],
            "measurements": [
                {
                    "measurement_id": item.measurement_id,
                    "name": item.name,
                    "value": round(item.value, 4),
                    "unit": item.unit,
                    "method": item.method,
                }
                for item in self.measurements
            ],
            "branches": [
                {
                    "branch_id": item.branch_id,
                    "source_node_id": item.source_node_id,
                    "target_node_id": item.target_node_id,
                    "path_length_pixels": round(item.path_length_pixels, 4),
                    "straight_distance_pixels": round(item.straight_distance_pixels, 4),
                    "orientation_degrees": round(item.orientation_degrees, 4),
                }
                for item in self.branches
            ],
            "junctions": [
                {
                    "node_id": item.node_id,
                    "x": item.x,
                    "y": item.y,
                    "branch_count": item.branch_count,
                    "branch_orientations": [
                        {"branch_id": branch_id, "angle_degrees": round(angle, 4)}
                        for branch_id, angle in item.branch_orientations
                    ],
                }
                for item in self.junctions
            ],
            "junction_terminal_distances": [
                {
                    "junction_node_id": item.junction_node_id,
                    "terminal_node_id": item.terminal_node_id,
                    "path_distance_pixels": round(item.path_distance_pixels, 4),
                    "straight_distance_pixels": round(item.straight_distance_pixels, 4),
                }
                for item in self.junction_terminal_distances
            ],
            "branch_pair_distances": [
                {
                    "junction_node_id": item.junction_node_id,
                    "first_branch_id": item.first_branch_id,
                    "second_branch_id": item.second_branch_id,
                    "via_junction_distance_pixels": round(
                        item.via_junction_distance_pixels, 4
                    ),
                    "midpoint_straight_distance_pixels": round(
                        item.midpoint_straight_distance_pixels, 4
                    ),
                    "angular_separation_degrees": round(
                        item.angular_separation_degrees, 4
                    ),
                }
                for item in self.branch_pair_distances
            ],
            "warnings": self.warnings,
            "errors": self.errors,
            "processing_time_ms": round(self.processing_time_ms, 2),
            "configuration": self.configuration,
        }
        if self.features is not None:
            data["features"] = (
                self.features.model_dump()
                if hasattr(self.features, "model_dump")
                else self.features
            )
        return data


class InspectionEngine:
    """Cloud-safe adapter around the repository's implemented OpenCV algorithms.

    No detector is fabricated when weights or a validated model adapter are absent.
    Production inspection rules therefore remain NOT_EVALUATED.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parents[3]
        self._model_status = self._discover_model_status()

    @staticmethod
    def available_variants() -> tuple[str, ...]:
        return (DEFAULT_VARIANT,)

    @property
    def model_status(self) -> ModelStatus:
        return self._model_status

    def inspect_harness(
        self,
        image: ImageArray,
        variant: str | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> InspectionResult:
        started = time.perf_counter()
        self._validate_image(image)
        selected_variant = variant or DEFAULT_VARIANT
        if selected_variant not in self.available_variants():
            raise InspectionInputError(f"Unsupported harness variant: {selected_variant}")
        resolved_config = self._validate_config(config or {})

        segmentation_service = HarnessSegmentationService(
            minimum_component_area_ratio=resolved_config["minimum_component_area_ratio"],
            closing_kernel_size=resolved_config["closing_kernel_size"],
            closing_iterations=resolved_config["closing_iterations"],
        )
        graph_service = HarnessGraphService(
            junction_cluster_radius=resolved_config["junction_cluster_radius"]
        )

        segmentation = segmentation_service.segment(image.copy())
        graph = graph_service.analyse(segmentation.binary_mask, base_image=image)
        feature_service = FeatureExtractionService(
            segmentation_service=segmentation_service,
            graph_service=graph_service,
        )
        features = feature_service.extract_features(
            image.copy(),
            mask=segmentation.binary_mask,
        )
        annotated = self._annotate_result(graph.overlay_image, graph.total_wire_length_pixels)
        branches = [
            BranchMeasurement(
                branch_id=branch.branch_id,
                source_node_id=branch.source_node_id,
                target_node_id=branch.target_node_id,
                path_length_pixels=branch.path_length_pixels,
                straight_distance_pixels=branch.straight_distance_pixels,
                orientation_degrees=branch.orientation_degrees,
            )
            for branch in graph.branches
        ]
        junctions = [
            JunctionMeasurement(
                node_id=node.node_id,
                x=node.point.x,
                y=node.point.y,
                branch_count=node.branch_count,
                branch_orientations=tuple(
                    (orientation.branch_id, orientation.angle_degrees)
                    for orientation in node.branch_orientations
                ),
            )
            for node in graph.nodes
            if node.node_type == "JUNCTION"
        ]
        terminal_distances = [
            JunctionTerminalMeasurement(
                junction_node_id=item.junction_node_id,
                terminal_node_id=item.terminal_node_id,
                path_distance_pixels=item.path_distance_pixels,
                straight_distance_pixels=item.straight_distance_pixels,
            )
            for item in graph.junction_terminal_distances
        ]
        branch_pair_distances = [
            BranchPairMeasurement(
                junction_node_id=item.junction_node_id,
                first_branch_id=item.first_branch_id,
                second_branch_id=item.second_branch_id,
                via_junction_distance_pixels=item.via_junction_distance_pixels,
                midpoint_straight_distance_pixels=item.midpoint_straight_distance_pixels,
                angular_separation_degrees=item.angular_separation_degrees,
            )
            for item in graph.branch_pair_distances
        ]
        measurements = [
            MeasurementValue(
                measurement_id="M-OCCUPANCY",
                name="Segmented harness occupancy",
                value=segmentation.occupied_percentage,
                unit="percent",
                method="OpenCV inverted Otsu mask after morphology and component filtering",
            ),
            MeasurementValue(
                measurement_id="M-CENTRELINE",
                name="Total skeleton centreline",
                value=graph.total_wire_length_pixels,
                unit="px",
                method="8-connected path: orthogonal step 1 px, diagonal step sqrt(2) px",
            ),
            MeasurementValue(
                measurement_id="M-BRANCHES",
                name="Resolved graph branches",
                value=float(len(graph.branches)),
                unit="count",
                method="Connected skeleton segments between clustered graph nodes",
            ),
            MeasurementValue(
                measurement_id="M-JUNCTIONS",
                name="Candidate junction clusters",
                value=float(len(graph.junctions)),
                unit="count",
                method="Clustered skeleton pixels with more than two neighbours",
            ),
            MeasurementValue(
                measurement_id="M-ENDPOINTS",
                name="Candidate endpoints",
                value=float(len(graph.endpoints)),
                unit="count",
                method="Skeleton pixels with one 8-connected neighbour",
            ),
            MeasurementValue(
                measurement_id="M-STRAIGHTNESS",
                name="Mean branch straightness ratio",
                value=features.geometric_features.mean_branch_straightness,
                unit="ratio",
                method="Straight euclidean distance divided by along-skeleton path length",
            ),
            MeasurementValue(
                measurement_id="M-MAX-BEND",
                name="Maximum local bend angle",
                value=features.geometric_features.max_bend_angle_deg,
                unit="degrees",
                method="Discrete windowed angle analysis along wire centerline",
            ),
        ]
        rules = self._rule_results(segmentation.occupied_percentage, graph)
        warnings = [
            "No trained object-detection model or validated model adapter is present; detections are empty.",
            "Segmentation and graph outputs are engineering feasibility evidence, not production decisions.",
            "No pixel-to-physical calibration is available; every dimensional value is reported in pixels.",
            "Connector, terminal, tape, missing-component, and routing rules are not evaluated.",
        ]
        if self.model_status.state == "UNSUPPORTED":
            warnings.insert(0, self.model_status.message)

        return InspectionResult(
            inspection_id=f"CLOUD-{datetime.now(UTC):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6].upper()}",
            timestamp=datetime.now(UTC),
            overall_status="NOT_EVALUATED",
            image_width=segmentation.image_width,
            image_height=segmentation.image_height,
            annotated_image=annotated,
            detected_components={},
            detections=[],
            rule_results=rules,
            model_status=self.model_status,
            selected_variant=selected_variant,
            warnings=warnings,
            errors=[],
            measurements=measurements,
            branches=branches,
            junctions=junctions,
            junction_terminal_distances=terminal_distances,
            branch_pair_distances=branch_pair_distances,
            processing_time_ms=(time.perf_counter() - started) * 1000.0,
            configuration=resolved_config,
            features=features,
        )

    def _discover_model_status(self) -> ModelStatus:
        configured_path = os.getenv("MODEL_WEIGHTS_PATH", "").strip()
        candidate: Path | None = None
        if configured_path:
            configured = Path(configured_path).expanduser()
            candidate = configured if configured.is_absolute() else self.project_root / configured
        else:
            model_directory = self.project_root / "data" / "models"
            if model_directory.is_dir():
                candidate = next(
                    (
                        path
                        for path in model_directory.rglob("*")
                        if path.is_file() and path.suffix.lower() in SUPPORTED_MODEL_SUFFIXES
                    ),
                    None,
                )

        if candidate is None or not candidate.is_file():
            return ModelStatus(
                state="MISSING",
                available=False,
                model_version="not-installed",
                model_format=None,
                device="cpu",
                message="No trained model weights were found. OpenCV engineering analysis remains available.",
            )
        return ModelStatus(
            state="UNSUPPORTED",
            available=False,
            model_version=candidate.stem,
            model_format=candidate.suffix.lower().lstrip("."),
            device="cpu",
            message=(
                f"Model file '{candidate.name}' exists, but this repository has no validated loader "
                "or class/rule adapter for it. Inference is intentionally disabled."
            ),
        )

    @staticmethod
    def _validate_image(image: ImageArray) -> None:
        if not isinstance(image, np.ndarray):
            raise InspectionInputError("Image must be an OpenCV NumPy array")
        if image.dtype != np.uint8:
            raise InspectionInputError("Image must use 8-bit channels")
        if image.ndim != 3 or image.shape[2] != 3:
            raise InspectionInputError("Image must be a decoded three-channel BGR image")
        if image.shape[0] < 16 or image.shape[1] < 16:
            raise InspectionInputError("Image dimensions are too small for inspection")

    @staticmethod
    def _validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
        minimum_ratio = float(config.get("minimum_component_area_ratio", 0.0002))
        closing_kernel = int(config.get("closing_kernel_size", 7))
        closing_iterations = int(config.get("closing_iterations", 2))
        junction_radius = int(config.get("junction_cluster_radius", 6))
        confidence_threshold = float(config.get("confidence_threshold", 0.5))
        if not 0.00001 <= minimum_ratio <= 0.01:
            raise InspectionInputError("Minimum component area ratio must be between 0.00001 and 0.01")
        if closing_kernel < 3 or closing_kernel > 31 or closing_kernel % 2 == 0:
            raise InspectionInputError("Closing kernel must be an odd integer from 3 to 31")
        if not 1 <= closing_iterations <= 8:
            raise InspectionInputError("Closing iterations must be from 1 to 8")
        if not 1 <= junction_radius <= 50:
            raise InspectionInputError("Junction cluster radius must be from 1 to 50")
        if not 0.01 <= confidence_threshold <= 1.0:
            raise InspectionInputError("Confidence threshold must be between 0.01 and 1.0")
        return {
            "minimum_component_area_ratio": minimum_ratio,
            "closing_kernel_size": closing_kernel,
            "closing_iterations": closing_iterations,
            "junction_cluster_radius": junction_radius,
            "confidence_threshold": confidence_threshold,
        }

    @staticmethod
    def _rule_results(occupied_percentage: float, graph: Any) -> list[RuleResult]:
        return [
            RuleResult(
                rule_id="EVIDENCE-SEGMENTATION",
                rule_name="Harness segmentation evidence",
                status="REVIEW_REQUIRED",
                actual_value=f"{occupied_percentage:.3f}% foreground",
                expected_value=None,
                message="Mask generated successfully, but no validated acceptance range is configured.",
            ),
            RuleResult(
                rule_id="EVIDENCE-TOPOLOGY",
                rule_name="Branch topology evidence",
                status="REVIEW_REQUIRED",
                actual_value=f"{len(graph.branches)} branches / {len(graph.junctions)} junction candidates",
                expected_value=None,
                message="Candidate graph extracted; model-specific topology reference is unavailable.",
            ),
            RuleResult("RULE-TERMINALS", "Terminal presence", "NOT_EVALUATED", None, None, "No validated terminal detector or class map is available."),
            RuleResult("RULE-CONNECTORS", "Connector presence and type", "NOT_EVALUATED", None, None, "No validated connector detector or class map is available."),
            RuleResult("RULE-TAPE", "Tape presence and colour", "NOT_EVALUATED", None, None, "No uploaded-image tape detector and no configured colour ROI/reference are available."),
            RuleResult("RULE-ROUTING", "Branch routing", "NOT_EVALUATED", None, None, "No model-specific reference route or validated routing tolerance is available."),
            RuleResult("RULE-DIMENSIONS", "Physical dimensional verification", "NOT_EVALUATED", None, None, "No calibrated pixel-to-physical-unit mapping is available."),
            RuleResult("RULE-COMPONENTS", "Missing or incorrect components", "NOT_EVALUATED", None, None, "Object detection weights and inspection rules are unavailable."),
        ]

    @staticmethod
    def _annotate_result(base_image: ImageArray, centreline_pixels: float) -> ImageArray:
        canvas = base_image.copy()
        height, width = canvas.shape[:2]
        banner_height = max(74, min(112, round(height * 0.075)))
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (width, banner_height), (48, 29, 8), -1)
        cv2.addWeighted(overlay, 0.9, canvas, 0.1, 0, canvas)
        title_scale = max(0.48, min(0.8, width / 1050))
        value_scale = max(0.75, min(1.25, width / 680))

        pixels_per_cm = 9.16
        try:
            from app.services.golden_reference_service import golden_reference_service
            ppm = golden_reference_service.get_configuration().get("calibration", {}).get("pixels_per_mm", 0.916)
            if ppm and ppm > 0:
                pixels_per_cm = round(float(ppm) * 10.0, 4)
        except Exception:
            pass
        centreline_cm = centreline_pixels / pixels_per_cm

        cv2.putText(canvas, "ENGINEERING ANALYSIS / CALIBRATED (cm)", (18, 29), cv2.FONT_HERSHEY_SIMPLEX, title_scale, (220, 232, 240), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"CENTRELINE {centreline_cm:,.1f} cm", (18, banner_height - 18), cv2.FONT_HERSHEY_DUPLEX, value_scale, (70, 220, 255), 2, cv2.LINE_AA)
        cv2.rectangle(canvas, (0, height - 34), (width, height), (48, 29, 8), -1)
        cv2.putText(canvas, "CALIBRATED METRIC MEASUREMENT (cm)", (14, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 232, 240), 1, cv2.LINE_AA)
        return canvas


def inspect_harness(
    image: ImageArray,
    variant: str | None = None,
    config: Mapping[str, Any] | None = None,
) -> InspectionResult:
    """Inspect an already-decoded OpenCV BGR image using implemented algorithms only."""
    return InspectionEngine().inspect_harness(image, variant=variant, config=config)
