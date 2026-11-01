from __future__ import annotations

from typing import Any
from app.services.rules.schemas import BranchTapingInput, EvidenceRef, InspectionContext, RuleResult

REACTION_PLAN = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


def evaluate_taping_standard(
    context: InspectionContext,
    pack_data: dict[str, Any],
) -> list[RuleResult]:
    results: list[RuleResult] = []
    taping_inputs = context.operator.branch_taping
    branch_types = pack_data.get("branch_types", {})

    if not taping_inputs:
        # Operator has not entered taping data -> NOT_EVALUATED
        results.append(
            RuleResult(
                rule_id="TAPING-DATA-INPUT",
                family="taping_standard",
                name="Branch Taping Inspection Data",
                source_doc="BT45-02 Branch Taping Standard",
                severity="MAJOR",
                status="NOT_EVALUATED",
                mandatory=True,
                expected="Operator branch taping inputs (laps, time, defects)",
                actual="None provided",
                reason="Branch taping laps and cycle time data not provided. Mandatory evaluation held.",
                reaction_plan=REACTION_PLAN,
            )
        )
        return results

    for item in taping_inputs:
        bid = item.branch_id
        btype = item.branch_type
        type_spec = branch_types.get(btype, {})

        min_laps = type_spec.get("min_laps", 19)
        max_laps = type_spec.get("max_laps", 30)
        allow_cross = type_spec.get("allow_cross_taping", False)

        evidence = [
            EvidenceRef(
                name="branch_taping_record",
                value=item.model_dump(),
                source="operator",
            )
        ]

        # 1. Lap count evaluation
        if item.laps is None:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-LAPS-{bid}",
                    family="taping_standard",
                    name=f"Finished Lap Count - Branch {bid} (Type {btype})",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="NOT_EVALUATED",
                    mandatory=True,
                    expected=f"{min_laps}-{max_laps} laps",
                    actual=None,
                    reason=f"Finished lap count not recorded for branch {bid}.",
                    reaction_plan=REACTION_PLAN,
                )
            )
        elif item.laps < min_laps or item.laps > max_laps:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-LAPS-{bid}",
                    family="taping_standard",
                    name=f"Finished Lap Count - Branch {bid} (Type {btype})",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="FAIL",
                    mandatory=True,
                    expected=f"{min_laps}-{max_laps} laps",
                    actual=f"{item.laps} laps",
                    evidence_refs=evidence,
                    reason=f"Branch {bid} lap count {item.laps} is outside standard {min_laps}-{max_laps} laps (Rank D).",
                    reaction_plan=REACTION_PLAN,
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-LAPS-{bid}",
                    family="taping_standard",
                    name=f"Finished Lap Count - Branch {bid} (Type {btype})",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="PASS",
                    mandatory=True,
                    expected=f"{min_laps}-{max_laps} laps",
                    actual=f"{item.laps} laps",
                    evidence_refs=evidence,
                    reason=f"Branch {bid} lap count {item.laps} conforms to Type {btype} specification ({min_laps}-{max_laps}).",
                    reaction_plan="",
                )
            )

        # 2. Cross Taping Rule (NO cross taping except X type)
        if item.cross_taping_present and not allow_cross:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-CROSS-{bid}",
                    family="taping_standard",
                    name=f"Cross Taping Prohibition - Branch {bid}",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="FAIL",
                    mandatory=True,
                    expected="No cross taping (permitted only on Type X)",
                    actual="Cross taping detected/reported",
                    evidence_refs=evidence,
                    reason=f"Cross taping detected on branch {bid} (Type {btype}). Cross taping is strictly forbidden on non-X types.",
                    reaction_plan=REACTION_PLAN,
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-CROSS-{bid}",
                    family="taping_standard",
                    name=f"Cross Taping Prohibition - Branch {bid}",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="PASS",
                    mandatory=True,
                    expected="No cross taping or authorized X-type",
                    actual="Compliant",
                    evidence_refs=evidence,
                    reason=f"No unauthorized cross taping on branch {bid}.",
                    reaction_plan="",
                )
            )

        # 3. Excess or Loose Taping (Defects at any location not allowed)
        if item.excess_taping or item.loose_taping:
            defect_names = []
            if item.excess_taping:
                defect_names.append("excess taping")
            if item.loose_taping:
                defect_names.append("loose taping")
            results.append(
                RuleResult(
                    rule_id=f"TAPING-DEFECT-{bid}",
                    family="taping_standard",
                    name=f"Taping Quality & Loose Tape Check - Branch {bid}",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="FAIL",
                    mandatory=True,
                    expected="No excess or loose taping (zero defect standard)",
                    actual=", ".join(defect_names),
                    evidence_refs=evidence,
                    reason=f"Taping defect on branch {bid}: {', '.join(defect_names)}. Zero defects allowed at any location.",
                    reaction_plan=REACTION_PLAN,
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-DEFECT-{bid}",
                    family="taping_standard",
                    name=f"Taping Quality & Loose Tape Check - Branch {bid}",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="CRITICAL",
                    status="PASS",
                    mandatory=True,
                    expected="No excess or loose taping",
                    actual="Zero defects",
                    evidence_refs=evidence,
                    reason=f"Branch {bid} taping free of excess or loose wraps.",
                    reaction_plan="",
                )
            )

        # 4. Cycle Time Rank Evaluation
        if item.cycle_time_seconds is None:
            results.append(
                RuleResult(
                    rule_id=f"TAPING-TIME-{bid}",
                    family="taping_standard",
                    name=f"Taping Cycle Time - Branch {bid}",
                    source_doc="BT45-02 Branch Taping Standard",
                    severity="MAJOR",
                    status="NOT_EVALUATED",
                    mandatory=False,
                    expected="Cycle time <= 40s (Rank C or better)",
                    actual=None,
                    reason=f"Taping cycle time not recorded for branch {bid}.",
                    reaction_plan="",
                )
            )
        else:
            t = float(item.cycle_time_seconds)
            rank = "D"
            if t <= 22.0:
                rank = "S"
            elif 23.0 <= t < 25.0:
                rank = "GAP"
            elif 25.0 <= t <= 30.0:
                rank = "A"
            elif 31.0 <= t <= 35.0:
                rank = "B"
            elif 36.0 <= t <= 40.0:
                rank = "C"
            else:
                rank = "D"

            if rank == "GAP":
                results.append(
                    RuleResult(
                        rule_id=f"TAPING-TIME-{bid}",
                        family="taping_standard",
                        name=f"Taping Cycle Time - Branch {bid}",
                        source_doc="BT45-02 Branch Taping Standard",
                        severity="MAJOR",
                        status="REVIEW",
                        mandatory=True,
                        expected="Cycle time <= 40s",
                        actual=f"{t:.1f}s (23-24s transition gap)",
                        evidence_refs=evidence,
                        reason=f"Branch {bid} cycle time {t:.1f}s falls into the 23-24s rank gap. Supervisory review required.",
                        reaction_plan=REACTION_PLAN,
                    )
                )
            elif rank == "D":
                results.append(
                    RuleResult(
                        rule_id=f"TAPING-TIME-{bid}",
                        family="taping_standard",
                        name=f"Taping Cycle Time - Branch {bid}",
                        source_doc="BT45-02 Branch Taping Standard",
                        severity="MAJOR",
                        status="FAIL",
                        mandatory=True,
                        expected="Rank S/A/B/C (<= 40s)",
                        actual=f"{t:.1f}s (Rank D)",
                        evidence_refs=evidence,
                        reason=f"Branch {bid} cycle time {t:.1f}s corresponds to Rank D (>= 41s). Exceeds allowable taping takt.",
                        reaction_plan=REACTION_PLAN,
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id=f"TAPING-TIME-{bid}",
                        family="taping_standard",
                        name=f"Taping Cycle Time - Branch {bid}",
                        source_doc="BT45-02 Branch Taping Standard",
                        severity="MAJOR",
                        status="PASS",
                        mandatory=True,
                        expected="Rank S/A/B/C (<= 40s)",
                        actual=f"{t:.1f}s (Rank {rank})",
                        evidence_refs=evidence,
                        reason=f"Branch {bid} cycle time {t:.1f}s achieves Rank {rank}.",
                        reaction_plan="",
                    )
                )

    return results
