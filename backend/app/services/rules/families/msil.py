from __future__ import annotations

from typing import Any
from app.services.rules.schemas import EvidenceRef, InspectionContext, RuleResult

REACTION_PLAN = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


def get_tolerance_for_nominal(
    nominal_mm: float,
    subject: str,
    pack_data: dict[str, Any],
    checkpoint_id: str | None = None,
    variant: str | None = None,
) -> tuple[float, float, str]:
    """Return (tol_pos, tol_neg, rule_source).

    Checks variant overrides first, then maps subject to column and finds
    the nominal class in the MSIL tolerance chart.
    """
    # 1. Variant specific override (drawing special tolerance) beats default
    if variant and checkpoint_id:
        v_overrides = pack_data.get("variant_overrides", {}).get(variant, {})
        if checkpoint_id in v_overrides:
            override = v_overrides[checkpoint_id]
            pos = float(override.get("tol_pos", 15.0))
            neg = float(override.get("tol_neg", 0.0))
            return pos, neg, f"Drawing Special Tolerance ({variant} {checkpoint_id})"

    # 2. Subject column mapping
    mapping = pack_data.get("subject_column_mapping", {})
    if subject in ("main_trunk", "branch_wire", "single_wire", "clamp_to_clamp"):
        col_name = subject
    else:
        col_name = mapping.get(subject, "branch_wire")

    # 3. Find nominal class
    nominal_classes = pack_data.get("nominal_classes", [])
    for cls in nominal_classes:
        min_n = float(cls.get("min_nominal_mm", 0.0))
        max_n = float(cls.get("max_nominal_mm", 999999.0))
        if min_n <= nominal_mm <= max_n:
            col_data = cls.get(col_name)
            if col_data:
                pos = col_data.get("tol_pos")
                neg = col_data.get("tol_neg")
                pos_val = float(pos) if pos is not None else 20.0
                neg_val = float(neg) if neg is not None else 0.0
                return pos_val, neg_val, f"MSIL Chart ({col_name} <= {max_n:.0f} mm)"

    return 20.0, 0.0, "MSIL Chart (default branch)"


def evaluate_msil_tolerances(
    context: InspectionContext,
    pack_data: dict[str, Any],
) -> list[RuleResult]:
    results: list[RuleResult] = []
    checkpoints = context.vision.checkpoints
    calibrated = context.vision.calibrated
    alignment_confidence = context.vision.alignment_confidence

    guard_cfg = pack_data.get("negative_side_guard", {})
    guard_enabled = guard_cfg.get("enabled", True)
    guard_ratio = float(guard_cfg.get("threshold_ratio", 0.80))

    if not calibrated or alignment_confidence < 0.85:
        # All dimensional rules become NOT_EVALUATED
        for cp in checkpoints:
            cid = cp.get("checkpoint_id", "CP-UNKNOWN")
            exp = cp.get("expected_value")
            results.append(
                RuleResult(
                    rule_id=f"MSIL-TOL-{cid}",
                    family="msil_tolerances",
                    name=f"MSIL Dimensional Tolerance {cid}",
                    source_doc="MSIL Tolerance Chart / Engineering Drawing",
                    severity="CRITICAL" if cp.get("type") in ("terminal", "node_distance") else "MAJOR",
                    status="NOT_EVALUATED",
                    mandatory=True,
                    expected=f"{exp} mm" if exp is not None else None,
                    actual=None,
                    reason="Optical calibration unverified or blueprint alignment confidence below 0.85; rule not evaluated.",
                    reaction_plan=REACTION_PLAN,
                )
            )
        return results

    for cp in checkpoints:
        cid = cp.get("checkpoint_id", "CP-UNKNOWN")
        ctype = cp.get("type", "terminal")
        exp = cp.get("expected_value") if cp.get("expected_value") is not None else cp.get("nominal_mm")
        det = cp.get("detected_value") if cp.get("detected_value") is not None else cp.get("measured_mm")
        ref_status = cp.get("status", "CONFIRMED")
        subject = cp.get("subject", "Protector-End branch" if ctype == "terminal" else "Clamp-Clamp")

        if exp is None:
            results.append(
                RuleResult(
                    rule_id=f"MSIL-TOL-{cid}",
                    family="msil_tolerances",
                    name=f"MSIL Dimensional Tolerance {cid}",
                    source_doc="MSIL Tolerance Chart / Engineering Drawing",
                    severity="MAJOR",
                    status="NOT_EVALUATED",
                    mandatory=False,
                    expected=None,
                    actual=None,
                    reason="No nominal blueprint dimension specified for checkpoint.",
                    reaction_plan="",
                )
            )
            continue

        tol_pos, tol_neg, rule_source = get_tolerance_for_nominal(
            nominal_mm=float(exp),
            subject=subject,
            pack_data=pack_data,
            checkpoint_id=cid,
            variant=context.variant,
        )

        tol_display = f"+{tol_pos:.1f}/-{tol_neg:.1f} mm" if tol_neg != tol_pos else f"±{tol_pos:.1f} mm"

        if det is None:
            results.append(
                RuleResult(
                    rule_id=f"MSIL-TOL-{cid}",
                    family="msil_tolerances",
                    name=f"MSIL Dimensional Tolerance {cid}",
                    source_doc=rule_source,
                    severity="CRITICAL" if ctype == "terminal" else "MAJOR",
                    status="NOT_EVALUATED",
                    mandatory=True,
                    expected=f"{exp:.1f} mm",
                    actual=None,
                    tolerance=tol_display,
                    deviation=None,
                    reason=f"Skeleton branch or physical distance for {cid} could not be resolved from workpiece image.",
                    reaction_plan=REACTION_PLAN,
                )
            )
            continue

        dev = round(float(det) - float(exp), 1)

        # Asymmetric tolerance check:
        # positive side cannot exceed tol_pos
        # negative side cannot drop below -tol_neg (for branch wire, tol_neg=0, so negative deviation is defect!)
        out_of_pos = dev > tol_pos
        out_of_neg = dev < -tol_neg

        # Negative-side guard (WI/PR/79 for clamp-to-clamp):
        # clamp-to-clamp values on negative side below 80% of tolerance flag REVIEW
        is_clamp_col = pack_data.get("subject_column_mapping", {}).get(subject) == "clamp_to_clamp"
        guard_triggered = False
        if guard_enabled and is_clamp_col and tol_neg > 0:
            if dev < - (tol_neg * guard_ratio) and not out_of_neg:
                guard_triggered = True

        evidence = [
            EvidenceRef(
                name="branch_measurement",
                value={"detected_mm": det, "nominal_mm": exp, "deviation_mm": dev},
                source="vision_graph",
                confidence=cp.get("confidence", 0.95),
            )
        ]

        calib_prov = context.vision.calibration_provenance or ""
        is_width_scaled = "width-scaled" in calib_prov

        if ref_status == "NEEDS_CONFIRMATION":
            status = "REVIEW"
            reason = f"Measurement {det:.1f} mm requires engineering confirmation of reference specification: {cp.get('notes', '')}"
            reaction = REACTION_PLAN
        elif out_of_pos:
            status = "FAIL"
            reason = f"Measurement {det:.1f} mm exceeds upper tolerance {tol_display} (deviation: {dev:+.1f} mm)"
            reaction = REACTION_PLAN
        elif out_of_neg:
            status = "FAIL"
            reason = f"Measurement {det:.1f} mm violates lower tolerance {tol_display} (deviation: {dev:+.1f} mm, negative length not permitted)"
            reaction = REACTION_PLAN
        elif guard_triggered:
            status = "REVIEW"
            reason = (
                f"Measurement {det:.1f} mm falls into negative-side guard region "
                f"(deviation {dev:+.1f} mm < -{guard_ratio*100:.0f}% of tolerance {tol_display}). "
                "Per WI/PR/79, process review is required."
            )
            reaction = REACTION_PLAN
        elif is_width_scaled:
            status = "REVIEW"
            reason = (
                f"Measurement {det:.1f} mm is within tolerance bounds ({dev:+.1f} mm), but calibration provenance "
                "is 'width-scaled'. Width-scaled calibration produces REVIEW (never PASS) on dimensional rules; "
                "in-situ yellow measuring tape or verified master calibration required for PASS disposition."
            )
            reaction = REACTION_PLAN
        else:
            status = "PASS"
            reason = f"Measurement {det:.1f} mm meets MSIL tolerance {tol_display} (deviation: {dev:+.1f} mm)"
            reaction = ""

        results.append(
            RuleResult(
                rule_id=f"MSIL-TOL-{cid}",
                family="msil_tolerances",
                name=f"MSIL Dimensional Tolerance {cid}",
                source_doc=rule_source,
                severity="CRITICAL" if ctype in ("terminal", "node_distance") else "MAJOR",
                status=status,
                mandatory=True,
                expected=f"{exp:.1f} mm",
                actual=f"{det:.1f} mm",
                tolerance=tol_display,
                deviation=f"{dev:+.1f} mm",
                evidence_refs=evidence,
                reason=reason,
                reaction_plan=reaction,
            )
        )

    return results
