from __future__ import annotations

import copy
import json
from pathlib import Path

import cv2
import numpy as np
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
    for p in [
        Path("data/test_images/harness_sample_01_raw_459x1024.jpeg"),
        Path("data/test_images/harness_sample_01_raw.jpeg"),
        Path("data/test_images/harness_sample_01.jpeg"),
    ]:
        if p.exists():
            from PIL import Image
            with Image.open(p) as img:
                if img.size == (459, 1024):
                    return p
    pytest.skip("459x1024 test image fixture not found")


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


def generate_synthetic_workpiece(mutate_branch_too_long: bool = False) -> tuple[np.ndarray, bytes]:
    """Generate a high-fidelity synthetic workpiece differing from the golden image:
    - Dimensions: 1800x560
    - Real in-situ yellow measuring tape with decimeter tick rhythm (provenance: tape-detected)
    - Corner fiducials ensuring high alignment confidence (>= 0.85)
    - Part number label sticker YH200502
    - Zero-crossing non-colliding routing for all 10 confirmed checkpoints
    - If mutate_branch_too_long is True, CP-T01 is routed 30 mm out of drawing tolerance.
    """
    h, w = 560, 1800
    img = np.full((h, w, 3), 245, dtype=np.uint8)

    # Alignment fiducials
    cv2.rectangle(img, (20, 20), (1780, 540), (210, 210, 210), 2)
    cv2.circle(img, (50, 50), 10, (100, 100, 100), -1)
    cv2.circle(img, (1750, 50), 10, (100, 100, 100), -1)
    cv2.circle(img, (50, 510), 10, (100, 100, 100), -1)
    cv2.circle(img, (1750, 510), 10, (100, 100, 100), -1)

    # Yellow measuring tape at top band y=8..38, x=100..1700 with decimeter ticks
    img[8:38, 100:1700] = (25, 215, 245)
    for tx in range(120, 1680, 196):
        img[8:38, tx:tx + 5] = (20, 20, 20)

    # Part number label sticker
    cv2.rectangle(img, (800, 250), (950, 300), (255, 255, 255), -1)
    cv2.putText(img, "YH200502", (810, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Clean non-colliding routes for confirmed checkpoints
    routes = {
        "CP-T08": [(439, 268), (584, 268)],
        "CP-T07": [(577, 481), (942, 481)],
        "CP-T06": [(469, 551), (873, 551)],
        "CP-T04": [(424, 409), (1204, 409)],
        "CP-NODE-N01-N02": [(200, 350), (200, 370), (740, 370)],
        "CP-NODE-N05-N06": [(750, 350), (750, 310), (1778, 310)],
        "CP-T01": [(130, 272), (130, 220), (921, 220)] if mutate_branch_too_long else [(130, 272), (130, 220), (852, 220)],
        "CP-T02": [(29, 385), (29, 160), (715, 160)],
        "CP-T03": [(356, 533), (356, 445), (1042, 445)],
        "CP-T05": [(405, 536), (405, 515), (1158, 515)],
    }

    for cid, pts in routes.items():
        cv2.polylines(img, [np.array(pts, dtype=np.int32)], False, (20, 20, 20), 4)

    success, png_bytes = cv2.imencode(".png", img)
    assert success
    return img, png_bytes.tobytes()


def test_evaluate_upload_confirmed_specs_accept(
    client: TestClient,
    full_operator_input_dict: dict,
) -> None:
    """Item 3: Evaluate confirmed specs on a synthetic workpiece differing from golden image -> assert ACCEPT.
    Asserts 0 FAIL, 0 REVIEW, 0 NOT_EVALUATED with tape-detected calibration.
    Prints image path, size, calibration provenance, alignment confidence, and evaluated rules.
    """
    img_bgr, img_bytes = generate_synthetic_workpiece(mutate_branch_too_long=False)
    h, w = img_bgr.shape[:2]

    resp = client.post(
        "/api/rules/evaluate/upload",
        files={"file": ("synthetic_workpiece.png", img_bytes, "image/png")},
        data={
            "variant": "YH200502",
            "part_no": "YH200502",
            "config_name": "confirmed",
            "operator_inputs_json": json.dumps(full_operator_input_dict),
        },
    )
    assert resp.status_code == 200, f"Error: {resp.text}"
    data = resp.json()

    print("\n--- AUDIT DIAGNOSTICS: CONFIRMED WORKPIECE INSPECTION ---")
    print(f"Image Source: Synthetic compliant test workpiece (differs from golden image)")
    print(f"Image Size: {w}x{h}")
    print(f"Calibration Provenance: {data['calibration_provenance']}")
    gate_align = next((r for r in data["rule_results"] if r["rule_id"] == "GATE-ALIGNMENT"), None)
    align_status = gate_align["status"] if gate_align else "N/A"
    print(f"Alignment Gate: {align_status}")
    print(f"Verdict: {data['verdict']}")
    print(f"Summary: {data['summary']}")
    print(f"Evaluated Rules Count: {len(data['rule_results'])}")
    print("Evaluated Rules Sample:")
    for r in data["rule_results"][:12]:
        print(f"  {r['rule_id']} [{r['status']}] ({r['family']}): {r['name']}")

    assert data["verdict"] == "ACCEPT"
    assert data["calibration_provenance"] == "tape-detected"
    assert data["summary"]["FAIL"] == 0
    assert data["summary"]["REVIEW"] == 0
    assert data["summary"]["NOT_EVALUATED"] == 0
    assert data["summary"]["PASS"] == 66
    assert "All mandatory quality inspection criteria satisfied." in data["reasons"]


def test_evaluate_upload_full_47_checkpoints_real_image_yields_hold(
    client: TestClient,
    board_crop_path: Path,
    full_operator_input_dict: dict,
) -> None:
    """Item 3: Full 47-checkpoint config on a real image yields HOLD, not ACCEPT."""
    img_bytes = board_crop_path.read_bytes()
    resp = client.post(
        "/api/rules/evaluate/upload",
        files={"file": (board_crop_path.name, img_bytes, "image/png")},
        data={
            "variant": "YH200502",
            "part_no": "YH200502",
            "operator_inputs_json": json.dumps(full_operator_input_dict),
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    print("\n--- AUDIT DIAGNOSTICS: FULL 47-CHECKPOINT REAL IMAGE INSPECTION ---")
    print(f"Image Path: {board_crop_path}")
    print(f"Calibration Provenance: {data['calibration_provenance']}")
    print(f"Verdict: {data['verdict']}")
    print(f"Summary: {data['summary']}")

    # Must yield HOLD because unconfirmed checkpoints and width-scaled calibration produce REVIEW
    assert data["verdict"] == "HOLD"
    assert data["calibration_provenance"] == "width-scaled"
    assert data["summary"]["REVIEW"] > 0


def test_evaluate_upload_branch_too_long_reject(
    client: TestClient,
    full_operator_input_dict: dict,
) -> None:
    """Item 3: Harness with one branch 30 mm too long yields REJECT."""
    _, img_bytes = generate_synthetic_workpiece(mutate_branch_too_long=True)

    resp = client.post(
        "/api/rules/evaluate/upload",
        files={"file": ("workpiece_too_long.png", img_bytes, "image/png")},
        data={
            "variant": "YH200502",
            "part_no": "YH200502",
            "config_name": "confirmed",
            "operator_inputs_json": json.dumps(full_operator_input_dict),
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    print("\n--- AUDIT DIAGNOSTICS: OUT-OF-SPEC BRANCH INSPECTION ---")
    print(f"Verdict: {data['verdict']}")
    print(f"Summary: {data['summary']}")

    assert data["verdict"] == "REJECT"
    assert data["summary"]["CRITICAL_FAIL"] >= 1
    t01_res = next((r for r in data["rule_results"] if r["rule_id"] == "MSIL-TOL-CP-T01"), None)
    assert t01_res is not None
    assert t01_res["status"] == "FAIL"
    assert "exceeds" in t01_res["reason"].lower()


def test_evaluate_upload_mutated_operator_sheet_reject(
    client: TestClient,
    full_operator_input_dict: dict,
) -> None:
    """Mutated operator check sheet (FRM19 item 3 set to NG) yields deterministic REJECT."""
    _, img_bytes = generate_synthetic_workpiece(mutate_branch_too_long=False)
    mutated_input = copy.deepcopy(full_operator_input_dict)
    mutated_input["check_sheet"]["checks"]["FRM19-03-NO-CKT-WRONG"]["first_piece"] = "NG"

    resp_reject = client.post(
        "/api/rules/evaluate/upload",
        files={"file": ("workpiece.png", img_bytes, "image/png")},
        data={
            "variant": "YH200502",
            "part_no": "YH200502",
            "config_name": "confirmed",
            "operator_inputs_json": json.dumps(mutated_input),
        },
    )
    assert resp_reject.status_code == 200
    data_reject = resp_reject.json()
    assert data_reject["verdict"] == "REJECT"
    assert data_reject["summary"]["CRITICAL_FAIL"] >= 1
    failed_ids = [r["rule_id"] for r in data_reject["rule_results"] if r["status"] == "FAIL"]
    assert "FRM19-03-NO-CKT-WRONG" in failed_ids


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
    assert "never pass" in res.reason.lower()
