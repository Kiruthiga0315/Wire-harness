import copy
import cv2
import numpy as np
import pytest

from app.services.golden_reference_service import golden_reference_service
from app.services.golden_inspection_service import golden_inspection_service


def test_golden_reference_configuration_and_unconfirmed():
    """Verify configuration loads cleanly and uncertain measurements are flagged NEEDS_CONFIRMATION."""
    config = golden_reference_service.get_configuration()
    checkpoints = config.get("checkpoints", [])
    
    assert len(checkpoints) >= 50, f"Expected at least 50 checkpoints, found {len(checkpoints)}"
    assert config.get("image_width") == 357
    assert config.get("image_height") == 767
    
    # Check that uncertain checkpoints have NEEDS_CONFIRMATION status
    uncertain_ids = ["CP-T12", "CP-T39", "CP-NODE-N11-N12"]
    for cid in uncertain_ids:
        cp = next((c for c in checkpoints if c["checkpoint_id"] == cid), None)
        assert cp is not None, f"Checkpoint {cid} missing from configuration"
        assert cp["status"] == "NEEDS_CONFIRMATION", f"Expected {cid} to be NEEDS_CONFIRMATION, got {cp['status']}"
        assert "notes" in cp and len(cp["notes"]) > 0


def test_golden_image_baseline_self_inspection():
    """Test golden reference image against itself as a baseline."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None, "Golden reference image could not be read"
    
    result = golden_inspection_service.inspect_image(golden_img)
    
    assert result.total_checkpoints == len(golden_reference_service.get_configuration()["checkpoints"])
    assert result.alignment_confidence >= 0.90
    assert result.passed_count > 0
    # Because unconfirmed items exist in the baseline specification, overall status should be REVIEW
    assert result.review_count > 0
    assert result.overall_status in ("REVIEW", "PASS")
    assert result.marked_image_data_url.startswith("data:image/png;base64,")


def test_controlled_measurement_deviation_fail():
    """Test that a checkpoint whose measurement exceeds tolerance is strictly marked FAIL."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None
    
    # Temporarily update CP-T01 to have a tight tolerance of 0.1 mm with a forced mismatch
    original_cp = golden_reference_service.get_checkpoint("CP-T01")
    assert original_cp is not None
    
    try:
        golden_reference_service.update_checkpoint("CP-T01", {
            "expected_value": 999.0, # Gross mismatch with detected value (~140 mm)
            "tolerance": 5.0,
            "status": "CONFIRMED"
        })
        
        result = golden_inspection_service.inspect_image(golden_img)
        t01_res = next(r for r in result.results if r.checkpoint_id == "CP-T01")
        
        assert t01_res.status == "FAIL", f"Expected FAIL for out-of-spec CP-T01, got {t01_res.status}"
        assert result.failed_count >= 1
        assert result.overall_status == "FAIL"
    finally:
        # Restore original
        golden_reference_service.update_checkpoint("CP-T01", original_cp)


def test_controlled_measurement_within_tolerance_pass():
    """Test that a confirmed checkpoint within tolerance passes."""
    golden_img = cv2.imread(str(golden_reference_service.golden_image_path))
    assert golden_img is not None
    
    # CP-T01 expected is 140 mm with 15 mm tolerance
    result = golden_inspection_service.inspect_image(golden_img)
    t01_res = next(r for r in result.results if r.checkpoint_id == "CP-T01")
    
    assert t01_res.status == "PASS"
    assert t01_res.deviation is not None
    assert abs(t01_res.deviation) <= t01_res.tolerance


def test_missing_component_detection():
    """Test that a blank white inspection table image detects missing wire harness components."""
    blank_img = np.full((1024, 459, 3), 250, dtype=np.uint8)
    
    result = golden_inspection_service.inspect_image(blank_img)
    
    # Components should not be detected on a blank image
    assert result.failed_count > 0
    assert result.overall_status == "FAIL"
    failed_items = [r for r in result.results if r.status == "FAIL"]
    assert any("not detected" in r.message.lower() for r in failed_items)


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
    
    assert len(lines) >= 51, f"Expected at least 50 data rows in CSV, got {len(lines)-1}"
