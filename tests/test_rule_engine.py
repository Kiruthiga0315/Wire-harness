from __future__ import annotations

import pytest

from app.services.rules.engine import rule_engine
from app.services.rules.families.gates import evaluate_pre_gates
from app.services.rules.families.msil import evaluate_msil_tolerances, get_tolerance_for_nominal
from app.services.rules.families.taping import evaluate_taping_standard
from app.services.rules.loader import RulePackValidationError, rule_pack_loader
from app.services.rules.schemas import (
    BranchTapingInput,
    CheckSheetEntry,
    FinalAssemblyCheckSheetInput,
    HarnessVerdict,
    InspectionContext,
    OperatorAttestation,
    OperatorInput,
    RuleResult,
    VisionEvidence,
)


# =============================================================================
# 1. BOUNDARY TESTS: MSIL TOLERANCE CLASSES & ASYMMETRIC BOUNDS
# =============================================================================

@pytest.fixture
def msil_pack():
    return rule_pack_loader.get_pack("msil_tolerances")


def test_msil_nominal_class_under_200_trunk(msil_pack):
    # <= 200 mm trunk: +-10 mm
    pos, neg, src = get_tolerance_for_nominal(150.0, "main_trunk", msil_pack)
    assert pos == 10.0
    assert neg == 10.0


def test_msil_nominal_class_under_200_branch_asymmetric(msil_pack):
    # <= 200 mm branch wire: +20 / -0 mm (asymmetric!)
    pos, neg, src = get_tolerance_for_nominal(150.0, "branch_wire", msil_pack)
    assert pos == 20.0
    assert neg == 0.0


def test_msil_nominal_class_201_to_500_branch(msil_pack):
    # 201-500 mm branch wire: +30 / -0 mm
    pos, neg, src = get_tolerance_for_nominal(300.0, "branch_wire", msil_pack)
    assert pos == 30.0
    assert neg == 0.0


def test_msil_nominal_class_501_to_2000_branch(msil_pack):
    # 501-2000 mm branch wire: +40 / -0 mm
    pos, neg, src = get_tolerance_for_nominal(1000.0, "branch_wire", msil_pack)
    assert pos == 40.0
    assert neg == 0.0


def test_msil_nominal_class_2001_to_5000_branch(msil_pack):
    # 2001-5000 mm branch wire: +50 / -0 mm
    pos, neg, src = get_tolerance_for_nominal(3000.0, "branch_wire", msil_pack)
    assert pos == 50.0
    assert neg == 0.0


def test_msil_clamp_clamp_nominal_class(msil_pack):
    # <= 200 mm: +-5 mm; 201-500: +-5 mm; 501-2000: +-10 mm
    pos1, neg1, _ = get_tolerance_for_nominal(100.0, "clamp_to_clamp", msil_pack)
    assert (pos1, neg1) == (5.0, 5.0)

    pos2, neg2, _ = get_tolerance_for_nominal(350.0, "clamp_to_clamp", msil_pack)
    assert (pos2, neg2) == (5.0, 5.0)

    pos3, neg3, _ = get_tolerance_for_nominal(800.0, "clamp_to_clamp", msil_pack)
    assert (pos3, neg3) == (10.0, 10.0)


def test_msil_branch_wire_boundary_evaluation(msil_pack):
    """Branch wire nominal 300 mm:
    +30 / -0 tolerance.
    330 mm (+30): PASS
    331 mm (+31): FAIL
    300 mm (+0): PASS
    299 mm (-1): FAIL (strict asymmetric: zero negative tolerance allowed)
    """
    def make_context(measured_val: float) -> InspectionContext:
        return InspectionContext(
            vision=VisionEvidence(
                calibrated=True,
                pixels_per_mm=1.96,
                calibration_provenance="tape-detected",
                checkpoints=[{
                    "checkpoint_id": "CP-TEST-BRANCH",
                    "subject": "Protector-End branch",
                    "nominal_mm": 300.0,
                    "measured_mm": measured_val,
                }],
            ),
            variant="DEFAULT",
        )

    # 330 mm -> PASS (exact upper boundary)
    res_330 = evaluate_msil_tolerances(make_context(330.0), msil_pack)
    assert res_330[0].status == "PASS"

    # 331 mm -> FAIL (upper boundary exceeded)
    res_331 = evaluate_msil_tolerances(make_context(331.0), msil_pack)
    assert res_331[0].status == "FAIL"

    # 300 mm -> PASS (nominal)
    res_300 = evaluate_msil_tolerances(make_context(300.0), msil_pack)
    assert res_300[0].status == "PASS"

    # 299 mm -> FAIL (negative deviation on asymmetric zero-neg branch)
    res_299 = evaluate_msil_tolerances(make_context(299.0), msil_pack)
    assert res_299[0].status == "FAIL"


def test_msil_negative_side_guard(msil_pack):
    """Clamp-to-clamp nominal 60 mm: tolerance +-5 mm.
    Deviation -3.0 mm (60% of -5 mm) -> PASS
    Deviation -4.2 mm (84% of -5 mm, below -80% threshold) -> REVIEW (negative_side_guard warning)
    Deviation -5.5 mm (exceeds -5 mm) -> FAIL
    """
    def make_clamp_context(measured_val: float) -> InspectionContext:
        return InspectionContext(
            vision=VisionEvidence(
                calibrated=True,
                pixels_per_mm=1.96,
                calibration_provenance="tape-detected",
                checkpoints=[{
                    "checkpoint_id": "CP-CLAMP-01",
                    "subject": "Clamp-Clamp",
                    "nominal_mm": 60.0,
                    "measured_mm": measured_val,
                }],
            ),
            variant="DEFAULT",
        )

    # 57.0 mm (dev = -3.0 mm, 60% of tol) -> PASS
    res_pass = evaluate_msil_tolerances(make_clamp_context(57.0), msil_pack)
    assert res_pass[0].status == "PASS"

    # 55.8 mm (dev = -4.2 mm, 84% of tol) -> REVIEW (negative-side guard triggered)
    res_review = evaluate_msil_tolerances(make_clamp_context(55.8), msil_pack)
    assert res_review[0].status == "REVIEW"
    assert "negative-side guard" in res_review[0].reason.lower()

    # 54.0 mm (dev = -6.0 mm, exceeds -5 mm) -> FAIL
    res_fail = evaluate_msil_tolerances(make_clamp_context(54.0), msil_pack)
    assert res_fail[0].status == "FAIL"


def test_msil_drawing_special_tolerance_override(msil_pack):
    """Drawing special tolerance in YH200502 for CP-T01 overrides default nominal class."""
    context = InspectionContext(
        vision=VisionEvidence(
            calibrated=True,
            pixels_per_mm=1.96,
            calibration_provenance="tape-detected",
            checkpoints=[{
                "checkpoint_id": "CP-T01",
                "subject": "Protector-End branch",
                "nominal_mm": 390.0,
                "measured_mm": 404.0,  # +14 mm (within special +15/-0 override)
            }],
        ),
        variant="YH200502",
    )
    res = evaluate_msil_tolerances(context, msil_pack)
    assert res[0].status == "PASS"
    assert "Drawing Special Tolerance" in res[0].source_doc


# =============================================================================
# 2. BOUNDARY TESTS: BT45-02 BRANCH TAPING STANDARD
# =============================================================================

@pytest.fixture
def taping_pack():
    return rule_pack_loader.get_pack("taping_standard")


def test_taping_w_branch_laps_boundaries(taping_pack):
    """W branch: 26 to 30 finished laps.
    26: PASS
    30: PASS
    25: FAIL (Rank D)
    31: FAIL (Rank D)
    """
    for laps, expected_status in [(26, "PASS"), (30, "PASS"), (25, "FAIL"), (31, "FAIL")]:
        ctx = InspectionContext(
            vision=VisionEvidence(),
            operator=OperatorInput(
                branch_taping=[
                    BranchTapingInput(
                        branch_id="BR-W",
                        branch_type="W",
                        laps=laps,
                        cycle_time_seconds=20.0,
                        cross_taping_present=False,
                        excess_taping=False,
                        loose_taping=False,
                    )
                ]
            ),
        )
        res = evaluate_taping_standard(ctx, taping_pack)
        laps_res = [r for r in res if "LAPS" in r.rule_id][0]
        assert laps_res.status == expected_status, f"Laps {laps} expected {expected_status}, got {laps_res.status}"


def test_taping_x_branch_allows_cross_taping(taping_pack):
    """X branch permits cross taping, while W/T/Y/V strictly prohibit cross taping."""
    # X branch with cross taping -> PASS
    ctx_x = InspectionContext(
        vision=VisionEvidence(),
        operator=OperatorInput(
            branch_taping=[
                BranchTapingInput(
                    branch_id="BR-X",
                    branch_type="X",
                    laps=29,
                    cycle_time_seconds=22.0,
                    cross_taping_present=True,
                    excess_taping=False,
                    loose_taping=False,
                )
            ]
        ),
    )
    res_x = evaluate_taping_standard(ctx_x, taping_pack)
    cross_res_x = [r for r in res_x if "CROSS" in r.rule_id][0]
    assert cross_res_x.status == "PASS"

    # W branch with cross taping -> FAIL (zero tolerance violation)
    ctx_w = InspectionContext(
        vision=VisionEvidence(),
        operator=OperatorInput(
            branch_taping=[
                BranchTapingInput(
                    branch_id="BR-W",
                    branch_type="W",
                    laps=28,
                    cycle_time_seconds=22.0,
                    cross_taping_present=True,
                    excess_taping=False,
                    loose_taping=False,
                )
            ]
        ),
    )
    res_w = evaluate_taping_standard(ctx_w, taping_pack)
    cross_res_w = [r for r in res_w if "CROSS" in r.rule_id][0]
    assert cross_res_w.status == "FAIL"


def test_taping_cycle_time_ranks_and_gap(taping_pack):
    """Cycle time ranks:
    <= 22s: Rank S (PASS)
    23-24s: Gap => REVIEW
    25-30s: Rank A (PASS)
    31-35s: Rank B (PASS)
    36-40s: Rank C (PASS)
    >= 41s: Rank D => FAIL
    """
    cases = [
        (20.0, "PASS"),
        (22.0, "PASS"),
        (23.5, "REVIEW"),  # 23-24s rank gap
        (28.0, "PASS"),
        (33.0, "PASS"),
        (38.0, "PASS"),
        (42.0, "FAIL"),  # Rank D
    ]
    for sec, exp_status in cases:
        ctx = InspectionContext(
            vision=VisionEvidence(),
            operator=OperatorInput(
                branch_taping=[
                    BranchTapingInput(
                        branch_id="BR-CYCLE",
                        branch_type="T",
                        laps=20,
                        cycle_time_seconds=sec,
                        cross_taping_present=False,
                        excess_taping=False,
                        loose_taping=False,
                    )
                ]
            ),
        )
        res = evaluate_taping_standard(ctx, taping_pack)
        time_res = [r for r in res if r.rule_id.startswith("TAPING-TIME-")][0]
        assert time_res.status == exp_status, f"Time {sec}s expected {exp_status}, got {time_res.status}"


# =============================================================================
# 3. FRM/PR/19 CHECK SHEET TESTS
# =============================================================================

@pytest.fixture
def frm19_pack():
    return rule_pack_loader.get_pack("final_assembly_frm19")


def test_frm19_check_sheet_ng_leads_to_fail(frm19_pack):
    """Any NG in first or last piece must trigger FAIL with REJECT action."""
    from app.services.rules.families.final_frm19 import evaluate_final_assembly_frm19

    checks = {
        f"FRM19-0{i}-X": CheckSheetEntry(first_piece="OK", last_piece="OK")
        for i in range(1, 10)
    }
    # Set item 3 (circuit check) to NG on last piece
    checks["FRM19-03-NO-CKT-WRONG"] = CheckSheetEntry(first_piece="OK", last_piece="NG", notes="Circuit crossed")

    ctx = InspectionContext(
        vision=VisionEvidence(),
        operator=OperatorInput(
            check_sheet=FinalAssemblyCheckSheetInput(
                part_no="YH200502",
                total_production_qty=10,
                label_serial_from=1001,
                label_serial_to=1010,
                label_serial_scrapped=0,
                checks=checks,
            )
        ),
        variant="YH200502",
    )
    results = evaluate_final_assembly_frm19(ctx, frm19_pack)
    ckt_res = [r for r in results if r.rule_id == "FRM19-03-NO-CKT-WRONG"][0]
    assert ckt_res.status == "FAIL"
    assert ckt_res.severity == "CRITICAL"


def test_frm19_check_sheet_corrected_leads_to_review(frm19_pack):
    """CORRECTED on first piece must trigger REVIEW with supervisor note."""
    from app.services.rules.families.final_frm19 import evaluate_final_assembly_frm19

    checks = {
        f"FRM19-0{i}-X": CheckSheetEntry(first_piece="OK", last_piece="OK")
        for i in range(1, 10)
    }
    checks["FRM19-06-NO-EXCESS-TAPE"] = CheckSheetEntry(
        first_piece="CORRECTED", last_piece="OK", notes="Excess tape unwrapped before run"
    )

    ctx = InspectionContext(
        vision=VisionEvidence(),
        operator=OperatorInput(
            check_sheet=FinalAssemblyCheckSheetInput(
                part_no="YH200502",
                total_production_qty=10,
                label_serial_from=1001,
                label_serial_to=1010,
                label_serial_scrapped=0,
                checks=checks,
            )
        ),
        variant="YH200502",
    )
    results = evaluate_final_assembly_frm19(ctx, frm19_pack)
    tape_res = [r for r in results if r.rule_id == "FRM19-06-NO-EXCESS-TAPE"][0]
    assert tape_res.status == "REVIEW"
    assert "CORRECTED" in tape_res.reason


def test_frm19_serial_reconciliation_mismatch(frm19_pack):
    """Serial reconciliation formula: (to - from + 1) - scrapped == total_qty.
    1020 - 1001 + 1 = 20. 20 - 2 = 18. If total_qty == 17, trigger REVIEW (MINOR).
    """
    from app.services.rules.families.final_frm19 import evaluate_final_assembly_frm19

    ctx = InspectionContext(
        vision=VisionEvidence(),
        operator=OperatorInput(
            check_sheet=FinalAssemblyCheckSheetInput(
                part_no="YH200502",
                total_production_qty=17,  # Mismatch: 18 != 17
                label_serial_from=1001,
                label_serial_to=1020,
                label_serial_scrapped=2,
            )
        ),
        variant="YH200502",
    )
    results = evaluate_final_assembly_frm19(ctx, frm19_pack)
    serial_res = [r for r in results if r.rule_id == "FRM19-SERIAL-RECONCILIATION"][0]
    assert serial_res.status == "REVIEW"
    assert serial_res.severity == "MINOR"


# =============================================================================
# 4. MISSING EVIDENCE & UNCALIBRATED VISION => HOLD (NEVER ACCEPT)
# =============================================================================

def test_uncalibrated_vision_holds_dimensional_rules():
    """If calibration is missing or uncalibrated, all dimensional rules must evaluate to
    NOT_EVALUATED and final verdict must be HOLD, never ACCEPT.
    """
    ctx = InspectionContext(
        vision=VisionEvidence(
            calibrated=False,
            pixels_per_mm=0.0,
            calibration_provenance="uncalibrated",
            checkpoints=[{
                "checkpoint_id": "CP-T01",
                "nominal_mm": 390.0,
                "measured_mm": None,
            }],
        ),
        variant="YH200502",
    )
    verdict = rule_engine.evaluate_context(ctx)
    assert verdict.verdict in ("HOLD", "REJECT")
    assert verdict.verdict != "ACCEPT"


def test_empty_check_sheet_and_taping_holds_mandatory_rules():
    """Missing operator check sheet and taping input results in HOLD."""
    ctx = InspectionContext(
        vision=VisionEvidence(
            calibrated=True,
            pixels_per_mm=1.96,
            calibration_provenance="tape-detected",
            alignment_confidence=0.98,
        ),
        operator=OperatorInput(check_sheet=None, branch_taping=[]),
        variant="YH200502",
    )
    verdict = rule_engine.evaluate_context(ctx)
    assert verdict.verdict == "HOLD"
    assert verdict.summary["NOT_EVALUATED"] > 0


# =============================================================================
# 5. VERDICT AGGREGATION & ZERO DEFAULT ACCEPTANCE
# =============================================================================

def test_verdict_aggregation_reject_priority():
    """Any CRITICAL or MAJOR FAIL immediately dictates REJECT disposition."""
    results = [
        RuleResult(rule_id="R1", family="f1", name="R1", source_doc="d1", severity="CRITICAL", status="FAIL", reason="Severe crack"),
        RuleResult(rule_id="R2", family="f2", name="R2", source_doc="d2", severity="MAJOR", status="PASS"),
        RuleResult(rule_id="R3", family="f3", name="R3", source_doc="d3", severity="MAJOR", status="NOT_EVALUATED", mandatory=True),
    ]
    verdict, summary, reasons = rule_engine.aggregate_disposition(results)
    assert verdict == "REJECT"
    assert summary["CRITICAL_FAIL"] == 1


def test_verdict_aggregation_accept_requires_all_mandatory_pass():
    """ACCEPT is never a default; every mandatory rule must PASS."""
    # With 1 REVIEW on mandatory rule -> HOLD
    results_held = [
        RuleResult(rule_id="R1", family="f1", name="R1", source_doc="d1", severity="MAJOR", status="PASS", mandatory=True),
        RuleResult(rule_id="R2", family="f2", name="R2", source_doc="d2", severity="MAJOR", status="REVIEW", mandatory=True),
    ]
    v_held, _, _ = rule_engine.aggregate_disposition(results_held)
    assert v_held == "HOLD"

    # All mandatory pass -> ACCEPT
    results_accept = [
        RuleResult(rule_id="R1", family="f1", name="R1", source_doc="d1", severity="MAJOR", status="PASS", mandatory=True),
        RuleResult(rule_id="R2", family="f2", name="R2", source_doc="d2", severity="MAJOR", status="PASS", mandatory=True),
    ]
    v_accept, _, _ = rule_engine.aggregate_disposition(results_accept)
    assert v_accept == "ACCEPT"


# =============================================================================
# 6. PTDB REPEAT SEVERITY WEIGHTING
# =============================================================================

def test_ptdb_repeat_severity_upgrade():
    """In PTDB, any concern with repeat_count >= 2, highlighted, or vehicle_reported
    must be upgraded to CRITICAL severity.
    """
    from app.services.rules.families.ptdb import evaluate_ptdb_regression

    ptdb_pack = rule_pack_loader.get_pack("ptdb_yh200502")
    ctx = InspectionContext(
        vision=VisionEvidence(calibrated=True, pixels_per_mm=1.96),
        operator=OperatorInput(),
        variant="YH200502",
    )
    results = evaluate_ptdb_regression(ctx, ptdb_pack)
    # Check PTDB-01 (repeat_count=3, vehicle_reported=True) -> CRITICAL
    ptdb_01 = [r for r in results if r.rule_id == "PTDB-01"][0]
    assert ptdb_01.severity == "CRITICAL"


# =============================================================================
# 7. RULE PACK LOADER VALIDATION
# =============================================================================

def test_loader_validates_required_packs():
    """All 5 core YAML packs must load and validate without error."""
    packs = rule_pack_loader.load_all_packs()
    assert len(packs) == 5
    assert "msil_tolerances" in packs
    assert "taping_standard" in packs
    assert "visual_inspection_wi79" in packs
    assert "final_assembly_frm19" in packs
    assert "ptdb_yh200502" in packs


def test_loader_rejects_missing_version(tmp_path):
    """Loader raises RulePackValidationError when version is missing."""
    bad_yaml = tmp_path / "bad_pack.yaml"
    bad_yaml.write_text("name: No Version Pack\n", encoding="utf-8")

    from app.services.rules.loader import RulePackLoader
    loader = RulePackLoader(rules_dir=tmp_path)
    with pytest.raises(RulePackValidationError):
        loader.get_pack("bad_pack")
