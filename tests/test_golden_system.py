import copy
import re
import cv2
import numpy as np
import pytest

from app.services.golden_reference_service import golden_reference_service
from app.services.golden_inspection_service import golden_inspection_service


def test_golden_reference_configuration_and_unconfirmed():
    """Verify configuration loads cleanly and uncertain measurements are flagged NEEDS_CONFIRMATION."""
    config = golden_reference_service.get_configuration()
    checkpoints = config.get("checkpoints", [])
    
    assert len(checkpoints) >= 40, f"Expected at least 40 checkpoints, found {len(checkpoints)}"
    assert config.get("image_width") == 1800
    assert config.get("image_height") == 560
    
    # Check that uncertain checkpoints have NEEDS_CONFIRMATION status
    uncertain_ids = ["CP-T12", "CP-T39", "CP-NODE-N11-N12"]
    for cid in uncertain_ids:
        cp = next((c for c in checkpoints if c["checkpoint_id"] == cid), None)
        assert cp is not None, f"Checkpoint {cid} missing from configuration"
        assert cp["status"] == "NEEDS_CONFIRMATION", f"Expected {cid} to be NEEDS_CONFIRMATION, got {cp['status']}"
        assert "notes" in cp and len(cp["notes"]) > 0


def test_every_confirmed_checkpoint_matches_drawing_note_source():
    """Item 2: Assert every CONFIRMED checkpoint's expected_value matches the number in its note/source."""
    config = golden_reference_service.get_configuration()
    confirmed = [cp for cp in config.get("checkpoints", []) if cp.get("status") == "CONFIRMED"]
    assert len(confirmed) == 10, f"Expected exactly 10 CONFIRMED checkpoints, found {len(confirmed)}"

    for cp in confirmed:
        cid = cp["checkpoint_id"]
        exp = cp["expected_value"]
        note = cp.get("notes", "")

        cm_match = re.search(r"(\d+(?:\.\d+)?)\s*cm", note, re.IGNORECASE)
        mm_match = re.search(r"(\d+(?:\.\d+)?)\s*mm", note, re.IGNORECASE)

        if cm_match:
            parsed = float(cm_match.group(1)) * 10.0
        elif mm_match:
            parsed = float(mm_match.group(1))
        else:
            pytest.fail(f"Could not parse numeric dimension from note of {cid}: {note}")

        assert abs(exp - parsed) < 1e-4, (
            f"Checkpoint {cid} expected_value ({exp}) does not match dimension parsed from note ({parsed} mm, note: {note})"
        )


def test_golden_image_baseline_self_inspection():
    """Test golden reference image against itself: width-scaled calibration and unconfirmed checkpoints produce REVIEW."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None, "Golden reference image could not be read"
    
    result = golden_inspection_service.inspect_image(golden_img)
    
    assert result.total_checkpoints == len(golden_reference_service.get_configuration()["checkpoints"])
    assert result.alignment_confidence >= 0.85
    # Because calibration is width-scaled and unconfirmed checkpoints exist, overall status must be REVIEW (HOLD)
    assert result.review_count > 0
    assert result.overall_status == "REVIEW"
    assert result.marked_image_data_url.startswith("data:image/png;base64,")


def test_controlled_measurement_deviation_fail():
    """Test that a checkpoint whose measurement exceeds tolerance is strictly marked FAIL under manual calibration."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None
    
    original_cp = golden_reference_service.get_checkpoint("CP-T01")
    assert original_cp is not None
    
    try:
        # Force a gross mismatch with force_drawing_override
        golden_reference_service.update_checkpoint("CP-T01", {
            "expected_value": 999.0,
            "force_drawing_override": True,
            "tolerance": 5.0,
            "status": "CONFIRMED"
        })
        
        # Run with manual calibration override
        result = golden_inspection_service.inspect_image(golden_img, override_pixels_per_mm=1.96078)
        t01_res = next(r for r in result.results if r.checkpoint_id == "CP-T01")
        
        assert t01_res.status == "FAIL", f"Expected FAIL for out-of-spec CP-T01, got {t01_res.status}"
        assert result.failed_count >= 1
    finally:
        # Restore original
        golden_reference_service.update_checkpoint("CP-T01", {
            "expected_value": original_cp["expected_value"],
            "force_drawing_override": True,
            "tolerance": original_cp["tolerance"],
            "status": original_cp["status"]
        })


def test_controlled_measurement_within_tolerance_pass():
    """Test that a confirmed checkpoint within tolerance passes under manual calibration."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None
    
    original_cp = golden_reference_service.get_checkpoint("CP-T01")
    assert original_cp is not None
    
    try:
        # First measure actual detected value on the image
        res_baseline = golden_inspection_service.inspect_image(golden_img, override_pixels_per_mm=1.96078)
        t01_detected = next(r for r in res_baseline.results if r.checkpoint_id == "CP-T01").detected_value
        assert t01_detected is not None and t01_detected > 0

        # Set expected_value exactly equal to detected_value for a compliant test
        golden_reference_service.update_checkpoint("CP-T01", {
            "expected_value": t01_detected,
            "force_drawing_override": True,
            "tolerance": 15.0,
            "status": "CONFIRMED"
        })

        result = golden_inspection_service.inspect_image(golden_img, override_pixels_per_mm=1.96078)
        t01_res = next(r for r in result.results if r.checkpoint_id == "CP-T01")
        
        assert t01_res.status == "PASS"
        assert t01_res.deviation is not None
        assert abs(t01_res.deviation) <= t01_res.tolerance
    finally:
        golden_reference_service.update_checkpoint("CP-T01", {
            "expected_value": original_cp["expected_value"],
            "force_drawing_override": True,
            "tolerance": original_cp["tolerance"],
            "status": original_cp["status"]
        })


def test_missing_component_detection():
    """Test that a blank white image fails alignment and triggers NOT_EVALUATED for dimensional rules."""
    blank_img = np.full((1024, 459, 3), 250, dtype=np.uint8)
    
    result = golden_inspection_service.inspect_image(blank_img)
    
    # Under low alignment confidence, all dimensional rules are NOT_EVALUATED
    not_eval_items = [r for r in result.results if r.status == "NOT_EVALUATED"]
    assert len(not_eval_items) == result.total_checkpoints
    assert result.overall_status in ("REVIEW", "HOLD")


def test_report_export_format():
    """Test CSV export contains correct headers and valid values."""
    csv_text = golden_reference_service.export_csv()
    lines = csv_text.strip().split("\n")
    headers = [h.strip() for h in lines[0].split(",")]
    
    required_cols = [
        "checkpoint_id", "type", "terminal_id", "node_id", "branch_id",
        "measurement_type", "expected_value", "unit", "tolerance", "confidence", "status"
    ]
    for col in required_cols:
        assert col in headers, f"Missing required column {col} in CSV export"
    
    assert len(lines) >= 40, f"Expected at least 40 data rows in CSV, got {len(lines)-1}"
