from __future__ import annotations

from typing import Any
from app.services.rules.schemas import EvidenceRef, InspectionContext, RuleResult

REACTION_PLAN = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


def evaluate_final_assembly_frm19(
    context: InspectionContext,
    pack_data: dict[str, Any],
) -> list[RuleResult]:
    """Evaluates Final Assembly Inspection Check Sheet FRM/PR/19 rev 10.

    Validates 9 checks x 2 pieces (first piece and last piece), part number matching,
    and barcode label serial reconciliation.
    """
    results: list[RuleResult] = []
    source_doc = pack_data.get("source_doc", "FRM/PR/19 rev 10")
    check_items = pack_data.get("check_items", [])
    sheet = context.operator.check_sheet

    # 1. Missing Check Sheet
    if sheet is None:
        results.append(
            RuleResult(
                rule_id="FRM19-CHECK-SHEET-INPUT",
                family="final_assembly_frm19",
                name="Final Assembly Check Sheet Submission",
                source_doc=source_doc,
                severity="CRITICAL",
                status="NOT_EVALUATED",
                mandatory=True,
                expected="Completed FRM/PR/19 check sheet for active shift",
                actual="None provided",
                reason="Final assembly check sheet FRM/PR/19 not submitted by line operator. Mandatory inspection held.",
                reaction_plan=REACTION_PLAN,
            )
        )
        return results

    # Evidence reference for the check sheet
    sheet_evidence = [
        EvidenceRef(
            name="check_sheet_data",
            value={
                "shift": sheet.shift,
                "date": sheet.date,
                "part_no": sheet.part_no,
                "associate_name": sheet.associate_name,
                "e_code": sheet.e_code,
                "total_production_qty": sheet.total_production_qty,
                "label_serial_from": sheet.label_serial_from,
                "label_serial_to": sheet.label_serial_to,
                "label_serial_scrapped": sheet.label_serial_scrapped,
            },
            source="operator",
        )
    ]

    # 2. Evaluate each of the 9 check items for first & last piece
    for item in check_items:
        item_id = item.get("id", "")
        item_name = item.get("name", item_id)
        severity = item.get("severity", "MAJOR")
        mandatory = item.get("mandatory", True)

        entry = sheet.checks.get(item_id)
        if entry is None:
            # Check item missing from sheet
            results.append(
                RuleResult(
                    rule_id=item_id,
                    family="final_assembly_frm19",
                    name=item_name,
                    source_doc=source_doc,
                    severity=severity,
                    status="NOT_EVALUATED",
                    mandatory=mandatory,
                    expected="first_piece: OK, last_piece: OK",
                    actual="Missing entry in check sheet",
                    evidence_refs=sheet_evidence,
                    reason=f"Check item '{item_name}' was not recorded in the submitted check sheet.",
                    reaction_plan=REACTION_PLAN,
                )
            )
            continue

        first = entry.first_piece
        last = entry.last_piece

        # NG on either piece => FAIL (REJECT)
        if first == "NG" or last == "NG":
            bad_pieces = []
            if first == "NG":
                bad_pieces.append("first piece")
            if last == "NG":
                bad_pieces.append("last piece")
            results.append(
                RuleResult(
                    rule_id=item_id,
                    family="final_assembly_frm19",
                    name=item_name,
                    source_doc=source_doc,
                    severity=severity,
                    status="FAIL",
                    mandatory=mandatory,
                    expected="first_piece: OK, last_piece: OK",
                    actual=f"first_piece: {first}, last_piece: {last}",
                    evidence_refs=sheet_evidence,
                    reason=f"Check item '{item_name}' recorded as NG on {', '.join(bad_pieces)}. {entry.notes or ''}".strip(),
                    reaction_plan=REACTION_PLAN,
                )
            )
        # CORRECTED on either piece => REVIEW (with note)
        elif first == "CORRECTED" or last == "CORRECTED":
            corr_pieces = []
            if first == "CORRECTED":
                corr_pieces.append("first piece")
            if last == "CORRECTED":
                corr_pieces.append("last piece")
            results.append(
                RuleResult(
                    rule_id=item_id,
                    family="final_assembly_frm19",
                    name=item_name,
                    source_doc=source_doc,
                    severity=severity,
                    status="REVIEW",
                    mandatory=mandatory,
                    expected="first_piece: OK, last_piece: OK",
                    actual=f"first_piece: {first}, last_piece: {last}",
                    evidence_refs=sheet_evidence,
                    reason=f"Check item '{item_name}' was CORRECTED on {', '.join(corr_pieces)}. Note: {entry.notes or 'No correction note recorded'}.",
                    reaction_plan=REACTION_PLAN,
                )
            )
        # Both OK => PASS
        elif first == "OK" and last == "OK":
            results.append(
                RuleResult(
                    rule_id=item_id,
                    family="final_assembly_frm19",
                    name=item_name,
                    source_doc=source_doc,
                    severity=severity,
                    status="PASS",
                    mandatory=mandatory,
                    expected="first_piece: OK, last_piece: OK",
                    actual="first_piece: OK, last_piece: OK",
                    evidence_refs=sheet_evidence,
                    reason=f"Check item '{item_name}' verified OK on both first and last piece.",
                )
            )
        else:
            results.append(
                RuleResult(
                    rule_id=item_id,
                    family="final_assembly_frm19",
                    name=item_name,
                    source_doc=source_doc,
                    severity=severity,
                    status="REVIEW",
                    mandatory=mandatory,
                    expected="first_piece: OK, last_piece: OK",
                    actual=f"first_piece: {first}, last_piece: {last}",
                    evidence_refs=sheet_evidence,
                    reason=f"Unrecognized check state for '{item_name}': first={first}, last={last}.",
                    reaction_plan=REACTION_PLAN,
                )
            )

    # 3. Part Number Matching
    expected_variant = (context.variant or context.part_no or "").strip().upper()
    sheet_part_no = (sheet.part_no or "").strip().upper()

    part_match = True
    mismatch_reasons = []

    if expected_variant and sheet_part_no and expected_variant not in sheet_part_no and sheet_part_no not in expected_variant:
        part_match = False
        mismatch_reasons.append(f"Check sheet part '{sheet_part_no}' does not match variant '{expected_variant}'")

    sticker_part = context.vision.sticker_data.get("part_number") or context.vision.sticker_data.get("text")
    if sticker_part:
        sticker_clean = str(sticker_part).strip().upper()
        if sheet_part_no and sheet_part_no not in sticker_clean and sticker_clean not in sheet_part_no:
            part_match = False
            mismatch_reasons.append(f"Check sheet part '{sheet_part_no}' does not match sticker OCR '{sticker_clean}'")

    if not part_match:
        results.append(
            RuleResult(
                rule_id="FRM19-PART-MATCH",
                family="final_assembly_frm19",
                name="Check Sheet Part Number Matching",
                source_doc=source_doc,
                severity="CRITICAL",
                status="FAIL",
                mandatory=True,
                expected=expected_variant,
                actual=sheet_part_no,
                evidence_refs=sheet_evidence,
                reason=f"Check sheet part number mismatch: {'; '.join(mismatch_reasons)}.",
                reaction_plan=REACTION_PLAN,
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="FRM19-PART-MATCH",
                family="final_assembly_frm19",
                name="Check Sheet Part Number Matching",
                source_doc=source_doc,
                severity="CRITICAL",
                status="PASS",
                mandatory=True,
                expected=expected_variant,
                actual=sheet_part_no,
                evidence_refs=sheet_evidence,
                reason=f"Check sheet part number '{sheet_part_no}' matches active variant and sticker OCR.",
            )
        )

    # 4. Label Serial Reconciliation
    # Formula: (label_serial_to - label_serial_from + 1) - label_serial_scrapped == total_production_qty
    calc_qty = (sheet.label_serial_to - sheet.label_serial_from + 1) - sheet.label_serial_scrapped
    if calc_qty == sheet.total_production_qty:
        results.append(
            RuleResult(
                rule_id="FRM19-SERIAL-RECONCILIATION",
                family="final_assembly_frm19",
                name="Barcode Label Serial Number Reconciliation",
                source_doc=source_doc,
                severity="MINOR",
                status="PASS",
                mandatory=False,
                expected=sheet.total_production_qty,
                actual=calc_qty,
                evidence_refs=sheet_evidence,
                reason=f"Serial range {sheet.label_serial_from}..{sheet.label_serial_to} minus {sheet.label_serial_scrapped} scrapped matches total production qty {sheet.total_production_qty}.",
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="FRM19-SERIAL-RECONCILIATION",
                family="final_assembly_frm19",
                name="Barcode Label Serial Number Reconciliation",
                source_doc=source_doc,
                severity="MINOR",
                status="REVIEW",
                mandatory=False,
                expected=sheet.total_production_qty,
                actual=calc_qty,
                evidence_refs=sheet_evidence,
                deviation=calc_qty - sheet.total_production_qty,
                reason=f"Label serial mismatch: ({sheet.label_serial_to} - {sheet.label_serial_from} + 1) - {sheet.label_serial_scrapped} scrapped = {calc_qty}, expected {sheet.total_production_qty}. Line supervisor review recommended.",
            )
        )

    return results
