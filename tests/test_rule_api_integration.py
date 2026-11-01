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
from app.services.rules.engine import rule_engine
from app.services.rules.schemas import (
    CheckSheetEntry,
    FinalAssemblyCheckSheetInput,
    InspectionContext,
    OperatorAttestation,
    OperatorInput,
    VisionEvidence,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def board_crop_path() -> Path:
    # 1800x560 inspection board crop
    for candidate in [
        Path("images_001/001/001_01_board_crop.png"),
        Path("data/golden_reference/golden_harness.png"),
    ]:
        if candidate.exists():
            return candidate
    pytest.skip("1800x560 inspection board crop image fixture not found")


@pytest.fixture
def raw_sample_path() -> Path:
    # 459x1024 unaligned / portrait raw capture
    p = Path("data/test_images/harness_sample_01.jpeg")
    if not p.exists():
        pytest.skip("459x1024 test image fixture not found")
    return p


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


def test_evaluate_upload_board_crop_1800x560_accept_and_mutated_reject(
    client: TestClient,
    board_crop_path: Path,
    full_operator_input_dict: dict,
) -> None:
    """Integration test on 1800x560 board crop:
    - Verifies ACCEPT disposition when confirmed checkpoints match engineering specifications,
      in-situ measuring tape provides verified calibration, and all operator entries pass.
    - Prints image path, size, calibration provenance, alignment confidence, and evaluated rules.
    - Mutates FRM19 check item 3 (circuit check) to NG and asserts deterministic REJECT.
    """
    img_bgr = cv2.imread(str(board_crop_path))
    assert img_bgr is not None
    h, w = img_bgr.shape[:2]
    img_bytes = board_crop_path.read_bytes()

    orig_cfg = golden_reference_service.get_configuration()

    try:
        # In confirmed production run, drawing-confirmed checkpoints are loaded
        conf_cfg = copy.deepcopy(orig_cfg)
        conf_cfg["checkpoints"] = [
            cp for cp in orig_cfg.get("checkpoints", []) if cp.get("status") == "CONFIRMED"
        ]
        golden_reference_service.save_configuration(conf_cfg)

        # 1. EVALUATE WITH FULL OPERATOR SHEET -> ACCEPT
        resp_accept = client.post(
            "/api/rules/evaluate/upload",
            files={"file": (board_crop_path.name, img_bytes, "image/png")},
            data={
                "variant": "YH200502",
                "part_no": "YH200502",
                "operator_inputs_json": json.dumps(full_operator_input_dict),
            },
        )
        assert resp_accept.status_code == 200, f"Error: {resp_accept.text}"
        data_accept = resp_accept.json()

        # Print audit diagnostics
        print("\n--- AUDIT DIAGNOSTICS: 1800x560 BOARD CROP INSPECTION ---")
        print(f"Image Path: {board_crop_path}")
        print(f"Image Size: {w}x{h} (board crop)")
        print(f"Calibration Provenance: {data_accept['calibration_provenance']}")
        print(f"Verdict: {data_accept['verdict']}")
        print(f"Summary: {data_accept['summary']}")
        print(f"Evaluated Rules Count: {len(data_accept['rule_results'])}")
        print("Evaluated Rules Sample:")
        for r in data_accept["rule_results"][:10]:
            print(f"  {r['rule_id']} [{r['status']}] ({r['family']}): {r['name']}")

        assert data_accept["verdict"] == "ACCEPT"
        assert data_accept["calibration_provenance"] == "tape-detected"
        assert data_accept["summary"]["FAIL"] == 0
        assert data_accept["summary"]["REVIEW"] == 0
        assert data_accept["summary"]["NOT_EVALUATED"] == 0
        assert "All mandatory quality inspection criteria satisfied." in data_accept["reasons"]

        # 2. MUTATED SHEET -> REJECT
        mutated_input = copy.deepcopy(full_operator_input_dict)
        mutated_input["check_sheet"]["checks"]["FRM19-03-NO-CKT-WRONG"]["first_piece"] = "NG"

        resp_reject = client.post(
            "/api/rules/evaluate/upload",
            files={"file": (board_crop_path.name, img_bytes, "image/png")},
            data={
                "variant": "YH200502",
                "part_no": "YH200502",
                "operator_inputs_json": json.dumps(mutated_input),
            },
        )
        assert resp_reject.status_code == 200
        data_reject = resp_reject.json()
        assert data_reject["verdict"] == "REJECT"
        assert data_reject["summary"]["CRITICAL_FAIL"] >= 1
        failed_ids = [r["rule_id"] for r in data_reject["rule_results"] if r["status"] == "FAIL"]
        assert "FRM19-03-NO-CKT-WRONG" in failed_ids
    finally:
        golden_reference_service.save_configuration(orig_cfg)


def test_459x1024_image_gets_hold_gate(
    client: TestClient,
    raw_sample_path: Path,
    full_operator_input_dict: dict,
) -> None:
    """Requirement: 459x1024 unaligned image gets HOLD (alignment/calibration gate)."""
    img_bgr = cv2.imread(str(raw_sample_path))
    assert img_bgr is not None
    h, w = img_bgr.shape[:2]
    img_bytes = raw_sample_path.read_bytes()

    resp = client.post(
        "/api/rules/evaluate/upload",
        files={"file": (raw_sample_path.name, img_bytes, "image/jpeg")},
        data={
            "variant": "YH200502",
            "part_no": "YH200502",
            "operator_inputs_json": json.dumps(full_operator_input_dict),
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    print("\n--- AUDIT DIAGNOSTICS: 459x1024 RAW IMAGE GATE INSPECTION ---")
    print(f"Image Path: {raw_sample_path}")
    print(f"Image Size: {w}x{h}")
    print(f"Calibration Provenance: {data['calibration_provenance']}")
    print(f"Verdict: {data['verdict']}")
    print(f"Summary: {data['summary']}")
    print(f"Hold Reasons: {data['reasons']}")

    # 459x1024 must get HOLD because perspective alignment / calibration fails the gate (< 0.90)
    assert data["verdict"] == "HOLD"
    gate_alignment = next((r for r in data["rule_results"] if r["rule_id"] == "GATE-ALIGNMENT"), None)
    assert gate_alignment is not None
    assert gate_alignment["status"] == "REVIEW"
    assert "alignment" in gate_alignment["reason"].lower()


def test_needs_confirmation_checkpoint_produces_review_hold_never_skipped() -> None:
    """Requirement: Any NEEDS_CONFIRMATION checkpoint tied to a mandatory rule must produce REVIEW (HOLD),
    and must NEVER be skipped.
    """
    ctx = InspectionContext(
        vision=VisionEvidence(
            calibrated=True,
            pixels_per_mm=1.96,
            calibration_provenance="tape-detected",
            alignment_confidence=1.0,
            checkpoints=[
                {
                    "checkpoint_id": "CP-MANDATORY-UNCONFIRMED",
                    "subject": "Protector-End branch",
                    "type": "terminal",
                    "nominal_mm": 150.0,
                    "measured_mm": 150.0,  # Exact measured distance
                    "status": "NEEDS_CONFIRMATION",  # Unconfirmed reference specification
                    "notes": "Manually placed checkpoint awaiting drawing confirmation",
                }
            ],
        ),
        operator=OperatorInput(master_sample_status="OK"),
        variant="YH200502",
        part_no="YH200502",
    )

    pack = rule_engine.loader.get_pack("msil_tolerances")
    from app.services.rules.families.msil import evaluate_msil_tolerances

    results = evaluate_msil_tolerances(ctx, pack)

    # 1. Checkpoint rule MUST be evaluated and present (never skipped)
    rule_ids = [r.rule_id for r in results]
    assert "MSIL-TOL-CP-MANDATORY-UNCONFIRMED" in rule_ids, "Checkpoint was skipped!"

    cp_rule = next(r for r in results if r.rule_id == "MSIL-TOL-CP-MANDATORY-UNCONFIRMED")
    assert cp_rule.mandatory is True

    # 2. Rule MUST produce REVIEW, never PASS
    assert cp_rule.status == "REVIEW", f"Expected REVIEW for unconfirmed checkpoint, got {cp_rule.status}"
    assert "confirmation" in cp_rule.reason.lower()

    # 3. Overall disposition MUST be HOLD (never ACCEPT)
    verdict, summary, reasons = rule_engine.aggregate_disposition(results)
    assert verdict == "HOLD", f"Expected HOLD for mandatory REVIEW, got {verdict}"


def test_width_scaled_calibration_produces_review_never_pass() -> None:
    """Requirement: Make width-scaled calibration produce REVIEW (never PASS) on dimensional rules."""
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
