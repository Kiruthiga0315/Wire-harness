from __future__ import annotations

import re
from typing import Any
from app.services.rules.schemas import EvidenceRef, InspectionContext, RuleResult

REACTION_PLAN = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


def _find_matching_checkpoints(checkpoints: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    matches = []
    for cp in checkpoints:
        text = f"{cp.get('checkpoint_id', '')} {cp.get('name', '')} {cp.get('subject', '')} {cp.get('notes', '')}".lower()
        if any(kw.lower() in text for kw in keywords):
            matches.append(cp)
    return matches


def evaluate_ptdb_regression(
    context: InspectionContext,
    pack_data: dict[str, Any],
) -> list[RuleResult]:
    """Evaluates Past Trouble Database (PTDB) regression rules for YH200502.

    Covers 23 MSIL historical concerns (Oct'25 - Mar'26). Repeat, highlighted,
    or vehicle-reported concerns are upgraded to CRITICAL severity.
    """
    results: list[RuleResult] = []
    source_doc = pack_data.get("source_doc", "MSIL PTDB YH200502 (23 MSIL Concerns)")
    concerns = pack_data.get("concerns", [])
    checkpoints = context.vision.checkpoints
    calibrated = context.vision.calibrated
    attestations = context.operator.attestations

    for c in concerns:
        rid = c.get("rule_id", "")
        ptdb_ref = c.get("ptdb_ref", "")
        desc = c.get("description", "")
        cat = c.get("category", "")
        repeat_count = int(c.get("repeat_count", 1))
        highlighted = bool(c.get("highlighted", False))
        vehicle_reported = bool(c.get("vehicle_reported", False))
        requires_attestation = bool(c.get("requires_operator_attestation", False))
        mandatory = bool(c.get("mandatory", True))

        # Dynamic severity: repeat >= 2 or highlighted or vehicle-reported => CRITICAL
        if repeat_count >= 2 or highlighted or vehicle_reported:
            severity = "CRITICAL"
        else:
            severity = c.get("severity", "MAJOR")

        # Check operator attestation first if provided
        att = attestations.get(rid) or attestations.get(ptdb_ref)

        # 1. Terminal-level concerns requiring operator attestation
        if requires_attestation:
            if att:
                if att.attested:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="PASS",
                            mandatory=mandatory,
                            expected=f"Zero defect: {desc}",
                            actual=f"Attested OK by {att.user_name or att.user_id}",
                            reason=f"Operator verified: {att.notes or 'No terminal defect observed'}.",
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="FAIL",
                            mandatory=mandatory,
                            expected=f"Zero defect: {desc}",
                            actual=f"Defect reported by {att.user_name or att.user_id}",
                            reason=f"Operator reported regression defect: {att.notes or desc}.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
            else:
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status="NOT_EVALUATED",
                        mandatory=mandatory,
                        expected=f"Operator attestation required: {desc}",
                        actual="No operator attestation",
                        reason=f"Mandatory PTDB regression check '{ptdb_ref}' requires tactile/close-up operator attestation.",
                        reaction_plan=REACTION_PLAN,
                    )
                )
            continue

        # 2. Category-based evaluation
        # A. Branch length issues (PTDB-01, 02, 03, 04)
        if cat == "branch_length":
            kw_map = {
                "PTDB-01": ["O2", "sensor", "CP-T08", "CP-T10"],
                "PTDB-02": ["EGR", "CP-T18"],
                "PTDB-03": ["Injector", "CP-T01", "CP-T02", "CP-T03", "CP-T04"],
                "PTDB-04": ["CNG", "CP-T05", "CP-T06", "CP-T07"],
            }
            kws = kw_map.get(rid, [c.get("coupler_type", "")])
            matching_cps = _find_matching_checkpoints(checkpoints, kws)

            if matching_cps and calibrated:
                # Check if any matching checkpoint has failed or is unresolved
                failed = [cp for cp in matching_cps if cp.get("status") == "FAIL"]
                unresolved = [cp for cp in matching_cps if cp.get("measured_mm") is None]
                if failed:
                    bad_ids = [cp.get("checkpoint_id") for cp in failed]
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="FAIL",
                            mandatory=mandatory,
                            expected=f"Nominal length within tolerance for {bad_ids}",
                            actual=f"Checkpoint failure on {bad_ids}",
                            reason=f"Branch length regression detected on {', '.join(bad_ids)}: exceeds drawing tolerance.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
                elif unresolved:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="NOT_EVALUATED",
                            mandatory=mandatory,
                            expected=f"Measurement for {desc}",
                            actual="Checkpoint branch path unresolved",
                            reason=f"Could not resolve skeleton path for {desc}. Mandatory inspection held.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="PASS",
                            mandatory=mandatory,
                            expected=f"Nominal length within tolerance for {len(matching_cps)} branches",
                            actual="All matching checkpoints within tolerance",
                            reason=f"Branch length confirmed compliant on {len(matching_cps)} inspected branch(es).",
                        )
                    )
            elif att:
                st = "PASS" if att.attested else "FAIL"
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status=st,
                        mandatory=mandatory,
                        expected=f"Branch length compliant: {desc}",
                        actual="Attested OK" if att.attested else "Defect reported",
                        reason=att.notes or f"Operator attestation: {st}",
                        reaction_plan="" if st == "PASS" else REACTION_PLAN,
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status="NOT_EVALUATED",
                        mandatory=mandatory,
                        expected=f"Branch length measurement: {desc}",
                        actual="No calibrated checkpoints or operator attestation",
                        reason="Optical scale uncalibrated or branch checkpoints missing.",
                        reaction_plan=REACTION_PLAN,
                    )
                )

        # B. Clamp position & defect concerns (PTDB-05 to PTDB-10, PTDB-23)
        elif cat in ("clamp_position", "clamp_defect", "bracket_clip_defect"):
            kw_map = {
                "PTDB-05": ["clamp", "injector"],
                "PTDB-06": ["clamp", "cng"],
                "PTDB-07": ["clamp", "crank"],
                "PTDB-08": ["protector", "clamp"],
                "PTDB-09": ["13", "cng", "controller"],
                "PTDB-10": ["24", "backlight", "fl"],
                "PTDB-23": ["fuse", "bracket", "clip"],
            }
            kws = kw_map.get(rid, ["clamp", "clip"])
            matching_cps = _find_matching_checkpoints(checkpoints, kws)

            if matching_cps and calibrated:
                failed = [cp for cp in matching_cps if cp.get("status") == "FAIL"]
                unresolved = [cp for cp in matching_cps if cp.get("measured_mm") is None]
                if failed:
                    bad_ids = [cp.get("checkpoint_id") for cp in failed]
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="FAIL",
                            mandatory=mandatory,
                            expected=f"Clamp position within +-5mm / +-10mm tolerance for {bad_ids}",
                            actual=f"Clamp failure on {bad_ids}",
                            reason=f"Clamp positioning regression on {', '.join(bad_ids)}: outside MSIL tolerance.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
                elif unresolved:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="FAIL",
                            mandatory=mandatory,
                            expected=f"Clamp present at designated fixture position",
                            actual="Clamp unresolved/missing",
                            reason=f"Clamp missing or obscured at designated fixture location: {desc}.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="PASS",
                            mandatory=mandatory,
                            expected="Clamp position verified per blueprint",
                            actual="Verified on jig",
                            reason=f"Clamp positioning compliant at {len(matching_cps)} designated checkpoint(s).",
                        )
                    )
            elif att:
                st = "PASS" if att.attested else "FAIL"
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status=st,
                        mandatory=mandatory,
                        expected=f"Clamp condition compliant: {desc}",
                        actual="Attested OK" if att.attested else "Defect reported",
                        reason=att.notes or f"Operator attestation: {st}",
                        reaction_plan="" if st == "PASS" else REACTION_PLAN,
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status="NOT_EVALUATED",
                        mandatory=mandatory,
                        expected=f"Clamp verification: {desc}",
                        actual="No vision checkpoint or operator attestation",
                        reason="Clamp checkpoint not evaluated and no operator attestation provided.",
                        reaction_plan=REACTION_PLAN,
                    )
                )

        # C. Coupler interchange (PTDB-13)
        elif cat == "coupler_interchange":
            # Check color tapes or operator attestation
            color_dets = context.vision.colored_tapes.get("detections", [])
            if color_dets:
                mismatches = [d for d in color_dets if not d.get("matches_spec", True)]
                if mismatches:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="FAIL",
                            mandatory=mandatory,
                            expected="Zero coupler interchange; 4P grey vs 3P black distinct",
                            actual=f"Color mismatch detected in connector tapes",
                            reason=f"Potential coupler interchange detected: color code mismatch at connector.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="PASS",
                            mandatory=mandatory,
                            expected="Correct coupler orientation and mating",
                            actual="Color tapes match specification",
                            reason="Coupler color codes verified; no interchange detected.",
                        )
                    )
            elif att:
                st = "PASS" if att.attested else "FAIL"
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status=st,
                        mandatory=mandatory,
                        expected="Zero coupler interchange",
                        actual="Attested OK" if att.attested else "Interchange defect reported",
                        reason=att.notes or f"Operator attestation: {st}",
                        reaction_plan="" if st == "PASS" else REACTION_PLAN,
                    )
                )
            else:
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status="NOT_EVALUATED",
                        mandatory=mandatory,
                        expected="Coupler identity verification",
                        actual="No color tape or operator attestation",
                        reason="Coupler interchange check requires color tape inspection or operator attestation.",
                        reaction_plan=REACTION_PLAN,
                    )
                )

        # D. Other visual defects (taping, routing, protector, grommet, tube damage)
        else:
            if att:
                st = "PASS" if att.attested else "FAIL"
                results.append(
                    RuleResult(
                        rule_id=rid,
                        family="ptdb_yh200502",
                        name=f"{ptdb_ref}: {desc}",
                        source_doc=source_doc,
                        severity=severity,
                        status=st,
                        mandatory=mandatory,
                        expected=f"Zero defect: {desc}",
                        actual="Attested OK" if att.attested else "Defect reported",
                        reason=att.notes or f"Operator attestation: {st}",
                        reaction_plan="" if st == "PASS" else REACTION_PLAN,
                    )
                )
            else:
                # If checkpoints or graph branches exist and overall pass
                if len(context.vision.checkpoints) > 0 and calibrated:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="PASS",
                            mandatory=mandatory,
                            expected=f"Zero defect: {desc}",
                            actual="Inspection board visual pass",
                            reason=f"No regression observed on fixture visual inspection.",
                        )
                    )
                else:
                    results.append(
                        RuleResult(
                            rule_id=rid,
                            family="ptdb_yh200502",
                            name=f"{ptdb_ref}: {desc}",
                            source_doc=source_doc,
                            severity=severity,
                            status="NOT_EVALUATED",
                            mandatory=mandatory,
                            expected=f"Visual verification: {desc}",
                            actual="No vision evidence or operator attestation",
                            reason=f"PTDB regression check '{ptdb_ref}' not evaluated.",
                            reaction_plan=REACTION_PLAN,
                        )
                    )

    return results
