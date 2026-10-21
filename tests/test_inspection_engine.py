from __future__ import annotations

import hashlib
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.inspection_engine import InspectionEngine, InspectionInputError


def _synthetic_harness() -> np.ndarray:
    image = np.full((240, 360, 3), 245, dtype=np.uint8)
    cv2.line(image, (35, 120), (325, 120), (20, 20, 20), 14)
    cv2.line(image, (180, 120), (180, 205), (20, 20, 20), 14)
    cv2.line(image, (100, 120), (70, 55), (20, 20, 20), 12)
    return image


def test_real_opencv_pipeline_returns_truthful_engineering_result(tmp_path) -> None:
    image = _synthetic_harness()
    original = image.copy()
    result = InspectionEngine(project_root=tmp_path).inspect_harness(image)

    assert result.overall_status == "NOT_EVALUATED"
    assert result.image_width == 360
    assert result.image_height == 240
    assert result.annotated_image.shape == image.shape
    assert not np.array_equal(result.annotated_image, image)
    assert np.array_equal(image, original), "inspection must not mutate the uploaded image"
    assert result.detections == []
    assert result.detected_components == {}
    assert result.model_status.state == "MISSING"
    assert result.model_status.device == "cpu"

    rules = {rule.rule_id: rule.status for rule in result.rule_results}
    assert rules["EVIDENCE-SEGMENTATION"] == "REVIEW_REQUIRED"
    assert rules["EVIDENCE-TOPOLOGY"] == "REVIEW_REQUIRED"
    for rule_id in (
        "RULE-TERMINALS",
        "RULE-CONNECTORS",
        "RULE-TAPE",
        "RULE-ROUTING",
        "RULE-DIMENSIONS",
        "RULE-COMPONENTS",
    ):
        assert rules[rule_id] == "NOT_EVALUATED"

    measurements = {item.measurement_id: item for item in result.measurements}
    assert measurements["M-OCCUPANCY"].value > 0
    assert measurements["M-CENTRELINE"].value > 0
    assert measurements["M-CENTRELINE"].unit == "px"
    assert all(junction.branch_count >= 1 for junction in result.junctions)
    assert all(
        0 <= angle < 360
        for junction in result.junctions
        for _, angle in junction.branch_orientations
    )


def test_model_file_without_validated_adapter_stays_disabled(tmp_path) -> None:
    model_directory = tmp_path / "data" / "models"
    model_directory.mkdir(parents=True)
    (model_directory / "customer-model.pt").write_bytes(b"not real weights")

    engine = InspectionEngine(project_root=tmp_path)
    assert engine.model_status.state == "UNSUPPORTED"
    assert engine.model_status.available is False
    result = engine.inspect_harness(_synthetic_harness())
    assert result.overall_status == "NOT_EVALUATED"
    assert result.detections == []


def test_invalid_inputs_and_configuration_are_rejected(tmp_path) -> None:
    engine = InspectionEngine(project_root=tmp_path)
    with pytest.raises(InspectionInputError, match="three-channel"):
        engine.inspect_harness(np.zeros((100, 100), dtype=np.uint8))
    with pytest.raises(InspectionInputError, match="odd integer"):
        engine.inspect_harness(_synthetic_harness(), config={"closing_kernel_size": 4})
    with pytest.raises(InspectionInputError, match="Unsupported harness variant"):
        engine.inspect_harness(_synthetic_harness(), variant="UNKNOWN")


def test_repeated_inspections_are_independent_and_memory_safe(tmp_path) -> None:
    engine = InspectionEngine(project_root=tmp_path)
    image = _synthetic_harness()
    original = image.copy()
    results = [engine.inspect_harness(image) for _ in range(3)]

    assert len({result.inspection_id for result in results}) == 3
    assert all(result.annotated_image.shape == image.shape for result in results)
    assert np.array_equal(image, original)


def test_existing_harness_fixture_produces_real_annotations_without_modification() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "test_images"
        / "harness_sample_01.jpeg.jpeg"
    )
    if not fixture.exists():
        pytest.skip("Private harness fixture is intentionally not committed")

    before = hashlib.sha256(fixture.read_bytes()).hexdigest()
    image = cv2.imread(str(fixture), cv2.IMREAD_COLOR)
    assert image is not None
    result = InspectionEngine(project_root=fixture.parents[2]).inspect_harness(image)
    after = hashlib.sha256(fixture.read_bytes()).hexdigest()

    assert result.annotated_image.shape == image.shape
    assert next(
        item.value for item in result.measurements if item.measurement_id == "M-CENTRELINE"
    ) > 0
    assert before == after
