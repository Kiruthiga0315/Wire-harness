from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import logging
from typing import Any
import uuid

import cv2
import numpy as np
from numpy.typing import NDArray

from app.services.calibration_service import resolve_calibration
from app.services.golden_inspection_service import golden_inspection_service
from app.services.rules.families.gates import evaluate_pre_gates
from app.services.rules.loader import rule_pack_loader
from app.services.rules.registry import rule_registry
from app.services.rules.schemas import (
    HarnessVerdict,
    HarnessVerdictType,
    InspectionContext,
    OperatorInput,
    RuleResult,
    VisionEvidence,
)

logger = logging.getLogger(__name__)

REACTION_PLAN_SEGREGATE = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


class RuleEngine:
    """Deterministic, explainable rule-based ACCEPT / REJECT / HOLD engine for wire harness inspection."""

    def __init__(self) -> None:
        self.loader = rule_pack_loader
        self.registry = rule_registry

    def evaluate_context(self, context: InspectionContext) -> HarnessVerdict:
        """Evaluates an already constructed InspectionContext across all active rule families.

        Deterministic, fast, and does not perform vision IO or feature extraction.
        """
        verdict_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        all_results: list[RuleResult] = []

        # 1. Pre-gate evaluation
        pre_gate_results = evaluate_pre_gates(
            image=None,
            calibrated=context.vision.calibrated,
            pixels_per_mm=context.vision.pixels_per_mm,
            alignment_confidence=context.vision.alignment_confidence,
            variant_selected=context.variant or context.part_no,
            image_quality=context.vision.image_quality,
        )
        # If image quality metrics were pre-computed in context:
        if context.vision.image_quality.failure_reasons:
            # Overwrite image quality result
            for r in pre_gate_results:
                if r.rule_id == "GATE-IMAGE-QUALITY":
                    r.status = "FAIL"
                    r.reason = f"Image quality gate failed: {'; '.join(context.vision.image_quality.failure_reasons)}"
                    r.reaction_plan = REACTION_PLAN_SEGREGATE

        all_results.extend(pre_gate_results)

        # 2. Evaluate all registered rule packs
        packs = self.loader.load_all_packs()
        pack_version = packs.get("msil_tolerances", {}).get("version", "1.0.0")

        for family_name in ["msil_tolerances", "taping_standard", "visual_inspection_wi79", "final_assembly_frm19", "ptdb_yh200502"]:
            evaluator = self.registry.get(family_name)
            if not evaluator:
                logger.warning("No evaluator registered for rule family '%s'", family_name)
                continue

            pack_data = packs.get(family_name, {})
            try:
                family_results = evaluator(context, pack_data)
                all_results.extend(family_results)
            except Exception as exc:
                logger.exception("Error evaluating rule family '%s': %s", family_name, exc)
                all_results.append(
                    RuleResult(
                        rule_id=f"ERR-{family_name.upper()}",
                        family=family_name,
                        name=f"Rule Family Execution: {family_name}",
                        source_doc="Rule Engine Internal",
                        severity="CRITICAL",
                        status="NOT_EVALUATED",
                        mandatory=True,
                        reason=f"Engine error evaluating family: {exc}",
                        reaction_plan=REACTION_PLAN_SEGREGATE,
                    )
                )

        # 3. Aggregate results and determine verdict
        verdict, summary, reasons = self.aggregate_disposition(all_results)

        reaction = REACTION_PLAN_SEGREGATE if verdict in ("REJECT", "HOLD") else ""

        return HarnessVerdict(
            verdict_id=verdict_id,
            timestamp=timestamp,
            verdict=verdict,
            variant=context.variant,
            part_no=context.part_no,
            rule_pack_version=pack_version,
            calibration_provenance=context.vision.calibration_provenance,
            image_hash=context.image_hash,
            rule_results=all_results,
            summary=summary,
            reaction_plan=reaction,
            reasons=reasons,
        )

    def evaluate_image(
        self,
        image: NDArray[np.uint8],
        operator_input: OperatorInput | None = None,
        variant: str = "YH200502",
        part_no: str = "YH200502",
    ) -> HarnessVerdict:
        """Full pipeline: Ingest image -> Pre-gates -> Evidence extraction -> Rule packs -> Verdict."""
        # 1. Compute Image Hash
        image_hash = ""
        if image is not None and hasattr(image, "tobytes"):
            image_hash = hashlib.sha256(image.tobytes()).hexdigest()

        # 2. Extract Calibration Evidence
        calib_info = resolve_calibration(image)
        calibrated = calib_info.calibrated
        pixels_per_mm = calib_info.pixels_per_mm
        calib_prov = calib_info.provenance

        # 3. Execute Golden Inspection pipeline (segmentation, graph, calibration, checkpoints)
        inspection_out = golden_inspection_service.inspect_image(
            image,
            target_variant=variant,
            min_alignment=0.85,
        )
        align_conf = getattr(inspection_out, "alignment_confidence", 1.0)
        
        # Checkpoints mapping
        checkpoints: list[dict[str, Any]] = []
        for cp in getattr(inspection_out, "results", []):
            checkpoints.append({
                "checkpoint_id": cp.checkpoint_id,
                "name": cp.checkpoint_id,
                "type": getattr(cp, "type", ""),
                "terminal_id": getattr(cp, "terminal_id", None),
                "node_id": getattr(cp, "node_id", None),
                "branch_id": getattr(cp, "branch_id", None),
                "nominal_mm": cp.expected_value,
                "expected_mm": cp.expected_value,
                "measured_mm": cp.detected_value,
                "detected_value": cp.detected_value,
                "unit": getattr(cp, "unit", "mm"),
                "tolerance": cp.tolerance,
                "deviation": cp.deviation,
                "status": cp.status,
                "confidence": getattr(cp, "confidence", 1.0),
                "message": getattr(cp, "message", ""),
                "roi_bbox": getattr(cp, "roi_bbox", None),
                "golden_coord": getattr(cp, "golden_coord", None),
                "test_coord": getattr(cp, "test_coord", None),
            })

        # Update calibration from inspection if tape detection didn't set it
        if not calibrated and getattr(inspection_out, "calibrated", False):
            calibrated = True
            pixels_per_mm = getattr(inspection_out, "pixels_per_mm", 0.0)
            calib_prov = "width-scaled"

        # Topology summary
        top_summary = getattr(inspection_out, "topology_summary", {}) or {}
        graph_branches = top_summary.get("branches", [])
        graph_nodes = top_summary.get("nodes", [])

        # Color tapes & sticker data
        color_out = getattr(inspection_out, "colored_tapes", {}) or {}
        sticker_out = getattr(inspection_out, "sticker", {}) or {}

        vision_evidence = VisionEvidence(
            calibrated=calibrated,
            pixels_per_mm=pixels_per_mm,
            calibration_provenance=calib_prov,
            alignment_confidence=align_conf,
            checkpoints=checkpoints,
            graph_branches=graph_branches if isinstance(graph_branches, list) else [],
            graph_nodes=graph_nodes if isinstance(graph_nodes, list) else [],
            colored_tapes=color_out if isinstance(color_out, dict) else {},
            sticker_data=sticker_out if isinstance(sticker_out, dict) else {},
            features={},
        )

        context = InspectionContext(
            vision=vision_evidence,
            operator=operator_input or OperatorInput(),
            variant=variant,
            part_no=part_no,
            image_hash=image_hash,
        )

        # 4. Evaluate context
        verdict = self.evaluate_context(context)

        return verdict

    @staticmethod
    def aggregate_disposition(
        rule_results: list[RuleResult],
    ) -> tuple[HarnessVerdictType, dict[str, int], list[str]]:
        """Determines final harness disposition based on factory rule taxonomy:

        - REJECT: Any CRITICAL or MAJOR rule FAIL, or any zero-tolerance failure.
        - HOLD: If not REJECT, and ANY mandatory rule is REVIEW or NOT_EVALUATED,
          or any pre-gate failed.
        - ACCEPT: Only when ALL mandatory rules PASS. ACCEPT is never a default.
        """
        summary: dict[str, int] = {
            "PASS": 0,
            "FAIL": 0,
            "REVIEW": 0,
            "NOT_EVALUATED": 0,
            "WAIVED": 0,
            "TOTAL": len(rule_results),
            "CRITICAL_FAIL": 0,
            "MAJOR_FAIL": 0,
            "MINOR_FAIL": 0,
        }
        reasons: list[str] = []

        has_reject = False
        has_hold = False

        for r in rule_results:
            st = r.status
            if st in summary:
                summary[st] += 1
            else:
                summary["NOT_EVALUATED"] += 1

            if st == "FAIL":
                if r.severity == "CRITICAL":
                    summary["CRITICAL_FAIL"] += 1
                elif r.severity == "MAJOR":
                    summary["MAJOR_FAIL"] += 1
                elif r.severity == "MINOR":
                    summary["MINOR_FAIL"] += 1

                # Pre-gates failure yields HOLD (re-capture required), not REJECT
                if r.family == "pre_gates":
                    has_hold = True
                    reasons.append(f"HOLD [{r.rule_id}] (PRE-GATE): {r.reason}")
                # Rejection triggers on product quality defects:
                elif r.severity in ("CRITICAL", "MAJOR") or getattr(r, "zero_tolerance", False):
                    has_reject = True
                    reasons.append(f"REJECT [{r.rule_id}] ({r.severity}): {r.reason}")
                else:
                    # Minor FAIL prompts review / hold if mandatory
                    if r.mandatory:
                        has_hold = True
                        reasons.append(f"HOLD [{r.rule_id}] (MINOR FAIL): {r.reason}")

            elif st in ("REVIEW", "NOT_EVALUATED"):
                if r.mandatory:
                    has_hold = True
                    reasons.append(f"HOLD [{r.rule_id}] ({st}): {r.reason}")

        if has_reject:
            final_verdict: HarnessVerdictType = "REJECT"
        elif has_hold:
            final_verdict = "HOLD"
        else:
            # ACCEPT only if there are rule results and all mandatory passed
            mandatory_results = [r for r in rule_results if r.mandatory]
            if mandatory_results and all(r.status == "PASS" for r in mandatory_results):
                final_verdict = "ACCEPT"
                reasons.append("All mandatory quality inspection criteria satisfied.")
            else:
                final_verdict = "HOLD"
                reasons.append("Inspection criteria incomplete or zero mandatory rules evaluated.")

        return final_verdict, summary, reasons


rule_engine = RuleEngine()
