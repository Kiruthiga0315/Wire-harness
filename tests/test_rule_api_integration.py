from __future__ import annotations

import copy
import json
from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.golden_inspection_service import golden_inspection_service
from app.services.golden_reference_service import golden_reference_service


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def test_image_path() -> Path:
    img_path = Path("data/test_images/harness_sample_01.jpeg")
    if not img_path.exists():
        pytest.skip(f"Test image fixture {img_path} not found")
    return img_path


@pytest.fixture
def full_operator_input_dict() -> dict:
    sheet_checks = {
        f"FRM19-0{i}-{name}": {"first_piece": "OK", "last_piece": "OK"}
        for i, name in [
            (1, "LENGTH"),
            (2, "PART-ATTACH"),
            (3, "NO-CKT-WRONG"),
            (4, "COLOUR-VTB"),
            (5, "VTB-PUNCHING"),
            (6, "NO-EXCESS-TAPE"),
            (7, "LABEL-ATTACH"),
            (8, "NO-LOOSE-TAPE"),
            (9, "NO-WRONG-TERM"),
        ]
    }
    return {
        "check_sheet": {
            "shift": "A",
            "part_no": "YH200502",
            "associate_name": "Test Associate",
            "e_code": "E1234",
            "total_production_qty": 1,
            "label_serial_from": 100001,
            "label_serial_to": 100001,
            "label_serial_scrapped": 0,
            "checks": sheet_checks,
        },
        "branch_taping": [
            {
                "branch_id": "B1",
                "branch_type": "W",
                "laps": 28,
                "cycle_time_seconds": 20.0,
            }
        ],
        "master_sample_status": "OK",
        "attestations": {
            k: {"user_id": "OP01", "user_name": "Line Operator", "attested": True}
            for k in [
                "WI79-REVISION",
                "WI79-DUMMY-SEALS",
                "WI79-TBO-CHECK",
                "WI79-CLAMP-COUNT-POS",
                "WI79-CLAMP-STAMP",
                "WI79-CIRCUIT-STAMP",
                "WI79-PACKING-TAPING",
                "WI79-HOUSING-TERMINAL",
                "WI79-NO-PART-MISSING",
                "WI79-BRANCH-SIZES",
                "WI79-PART-LABEL",
                "PTDB-01",
                "PTDB-02",
                "PTDB-03",
                "PTDB-04",
                "PTDB-05",
                "PTDB-06",
                "PTDB-07",
                "PTDB-08",
                "PTDB-09",
                "PTDB-10",
                "PTDB-11",
                "PTDB-12",
                "PTDB-13",
                "PTDB-14",
                "PTDB-15",
                "PTDB-16",
                "PTDB-17",
                "PTDB-18",
                "PTDB-19",
                "PTDB-20",
                "PTDB-21",
                "PTDB-22",
                "PTDB-23",
            ]
        },
    }


def test_evaluate_upload_real_image_accept_and_mutated_reject(
    client: TestClient,
    test_image_path: Path,
    full_operator_input_dict: dict,
) -> None:
    """Integration test:
    1. Runs a real workpiece image through POST /api/rules/evaluate/upload with full operator inputs.
    2. Confirms ACCEPT disposition when all vision evidence and check sheets pass.
    3. Mutates check sheet item 3 (circuit check) to NG and asserts deterministic REJECT.
    """
    img_bgr = cv2.imread(str(test_image_path))
    assert img_bgr is not None
    img_bytes = test_image_path.read_bytes()

    orig_cfg = golden_reference_service.get_configuration()

    try:
        # Align golden configuration to detected checkpoints on workpiece image
        raw_res = golden_inspection_service.inspect_image(img_bgr)
        det_map = {
            r.checkpoint_id: r.detected_value
            for r in raw_res.results
            if r.detected_value is not None
        }

        new_cfg = copy.deepcopy(orig_cfg)
        active_cps = []
        for cp in new_cfg.get("checkpoints", []):
            cid = cp["checkpoint_id"]
            if cid in det_map:
                cp["expected_value"] = det_map[cid]
                cp["status"] = "CONFIRMED"
                active_cps.append(cp)
        new_cfg["checkpoints"] = active_cps
        golden_reference_service.save_configuration(new_cfg)

        # 1. EVALUATE WITH FULL VALID OPERATOR SHEET -> ACCEPT
        resp_accept = client.post(
            "/api/rules/evaluate/upload",
            files={"file": (test_image_path.name, img_bytes, "image/jpeg")},
            data={
                "variant": "YH200502",
                "part_no": "YH200502",
                "operator_inputs_json": json.dumps(full_operator_input_dict),
            },
        )
        assert resp_accept.status_code == 200, f"Error: {resp_accept.text}"
        data_accept = resp_accept.json()
        assert data_accept["verdict"] == "ACCEPT", f"Expected ACCEPT, got {data_accept['verdict']}"
        assert data_accept["summary"]["FAIL"] == 0
        assert data_accept["summary"]["REVIEW"] == 0
        assert data_accept["summary"]["NOT_EVALUATED"] == 0
        assert "All mandatory quality inspection criteria satisfied." in data_accept["reasons"]

        # 2. EVALUATE WITH MUTATED OPERATOR SHEET (item 3 NG) -> REJECT
        mutated_input = copy.deepcopy(full_operator_input_dict)
        mutated_input["check_sheet"]["checks"]["FRM19-03-NO-CKT-WRONG"]["first_piece"] = "NG"

        resp_reject = client.post(
            "/api/rules/evaluate/upload",
            files={"file": (test_image_path.name, img_bytes, "image/jpeg")},
            data={
                "variant": "YH200502",
                "part_no": "YH200502",
                "operator_inputs_json": json.dumps(mutated_input),
            },
        )
        assert resp_reject.status_code == 200, f"Error: {resp_reject.text}"
        data_reject = resp_reject.json()
        assert data_reject["verdict"] == "REJECT", f"Expected REJECT, got {data_reject['verdict']}"
        assert data_reject["summary"]["CRITICAL_FAIL"] >= 1
        failed_ids = [
            r["rule_id"] for r in data_reject["rule_results"] if r["status"] == "FAIL"
        ]
        assert "FRM19-03-NO-CKT-WRONG" in failed_ids
    finally:
        golden_reference_service.save_configuration(orig_cfg)


def test_width_scaled_calibration_produces_review_never_pass() -> None:
    """Requirement: Make width-scaled calibration produce REVIEW (never PASS) on dimensional rules."""
    from app.services.rules.engine import rule_engine
    from app.services.rules.schemas import InspectionContext, VisionEvidence

    ctx = InspectionContext(
        vision=VisionEvidence(
            calibrated=True,
            pixels_per_mm=1.0,
            calibration_provenance="width-scaled",  # Proportional board scaling without tape
            alignment_confidence=1.0,
            checkpoints=[
                {
                    "checkpoint_id": "CP-TEST-WIDTH-SCALED",
                    "subject": "Protector-End branch",
                    "nominal_mm": 100.0,
                    "measured_mm": 100.0,  # Exact nominal match
                    "status": "CONFIRMED",
                }
            ],
        ),
        variant="YH200502",
        part_no="YH200502",
    )

    pack = rule_engine.loader.get_pack("msil_tolerances")
    from app.services.rules.families.msil import evaluate_msil_tolerances

    results = evaluate_msil_tolerances(ctx, pack)
    assert len(results) == 1
    res = results[0]

    # MUST be REVIEW, never PASS, because calibration provenance is width-scaled
    assert res.status == "REVIEW", f"Expected REVIEW, got {res.status}"
    assert "width-scaled" in res.reason.lower()
    assert "review (never pass)" in res.reason.lower()
