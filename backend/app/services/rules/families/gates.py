from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from app.services.rules.schemas import EvidenceRef, ImageQualityMetrics, RuleResult

REACTION_PLAN_SEGREGATE = (
    "Pink tag + Red tape, segregate, inform supervisor/line leader; "
    "no rework at visual-inspection stage; record NG details"
)


def evaluate_image_quality(image: NDArray[np.uint8]) -> ImageQualityMetrics:
    if image is None or not hasattr(image, "shape") or image.ndim != 3:
        return ImageQualityMetrics(
            passed=False,
            failure_reasons=["Invalid or undecodable image payload"],
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    mean_val = float(np.mean(gray))

    # Clipping ratios
    total_pixels = float(gray.size)
    dark_clipped = float(np.count_nonzero(gray <= 5)) / total_pixels
    bright_clipped = float(np.count_nonzero(gray >= 250)) / total_pixels

    reasons: list[str] = []
    # Sharpness threshold
    if laplacian_var < 80.0:
        reasons.append(f"Image is blurry (Laplacian variance {laplacian_var:.1f} < 80.0)")

    # Brightness threshold
    if mean_val < 35.0:
        reasons.append(f"Image is underexposed (mean brightness {mean_val:.1f} < 35.0)")
    elif mean_val > 230.0:
        reasons.append(f"Image is overexposed (mean brightness {mean_val:.1f} > 230.0)")

    if dark_clipped > 0.08:
        reasons.append(f"Severe dark pixel clipping ({dark_clipped * 100:.1f}% > 8%)")
    if bright_clipped > 0.08:
        reasons.append(f"Severe highlight pixel clipping ({bright_clipped * 100:.1f}% > 8%)")

    passed = len(reasons) == 0
    return ImageQualityMetrics(
        sharpness_laplacian=round(laplacian_var, 2),
        mean_brightness=round(mean_val, 2),
        dark_clipping_ratio=round(dark_clipped, 4),
        bright_clipping_ratio=round(bright_clipped, 4),
        passed=passed,
        failure_reasons=reasons,
    )


def evaluate_pre_gates(
    image: NDArray[np.uint8] | None = None,
    *,
    calibrated: bool,
    pixels_per_mm: float,
    alignment_confidence: float,
    min_alignment: float = 0.85,
    occupied_percentage: float | None = None,
    variant_selected: str | None = None,
    image_quality: ImageQualityMetrics | None = None,
) -> list[RuleResult]:
    results: list[RuleResult] = []

    # 1. Image Quality Gate
    if image is not None:
        iq = evaluate_image_quality(image)
    elif image_quality is not None:
        iq = image_quality
    else:
        iq = ImageQualityMetrics(passed=True)
    if not iq.passed:
        results.append(
            RuleResult(
                rule_id="GATE-IMAGE-QUALITY",
                family="pre_gates",
                name="Image Quality Verification Gate",
                source_doc="Engineering Pre-Inspection Gate",
                severity="CRITICAL",
                status="FAIL",
                mandatory=True,
                expected="Sharpness >= 80, Brightness [35, 230], Clipping <= 8%",
                actual=f"Sharpness={iq.sharpness_laplacian}, Brightness={iq.mean_brightness}",
                evidence_refs=[
                    EvidenceRef(
                        name="image_quality_metrics",
                        value=iq.model_dump(),
                        source="vision_quality",
                    )
                ],
                reason=f"Image quality pre-gate failed: {'; '.join(iq.failure_reasons)}. Re-capture required.",
                reaction_plan=REACTION_PLAN_SEGREGATE,
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="GATE-IMAGE-QUALITY",
                family="pre_gates",
                name="Image Quality Verification Gate",
                source_doc="Engineering Pre-Inspection Gate",
                severity="CRITICAL",
                status="PASS",
                mandatory=True,
                expected="Sharpness >= 80, Brightness [35, 230], Clipping <= 8%",
                actual=f"Sharpness={iq.sharpness_laplacian}, Brightness={iq.mean_brightness}",
                evidence_refs=[
                    EvidenceRef(
                        name="image_quality_metrics",
                        value=iq.model_dump(),
                        source="vision_quality",
                    )
                ],
                reason="Image quality parameters (sharpness, exposure, dynamic range) meet inspection standards.",
                reaction_plan="",
            )
        )

    # 2. Calibration Gate
    if not calibrated or pixels_per_mm <= 0:
        results.append(
            RuleResult(
                rule_id="GATE-CALIBRATION",
                family="pre_gates",
                name="Optical Calibration Gate",
                source_doc="Factory Optical Calibration Standard",
                severity="CRITICAL",
                status="FAIL",
                mandatory=True,
                expected="Calibrated pixels_per_mm > 0 with valid provenance",
                actual=f"Calibrated={calibrated}, pixels_per_mm={pixels_per_mm}",
                reason="Workpiece image lacks verified optical scale calibration. Re-capture with yellow measuring tape or valid jig alignment.",
                reaction_plan=REACTION_PLAN_SEGREGATE,
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="GATE-CALIBRATION",
                family="pre_gates",
                name="Optical Calibration Gate",
                source_doc="Factory Optical Calibration Standard",
                severity="CRITICAL",
                status="PASS",
                mandatory=True,
                expected="Calibrated pixels_per_mm > 0",
                actual=f"Calibrated={calibrated}, pixels_per_mm={pixels_per_mm:.4f}",
                reason="Optical calibration verified from inspection board measuring standard.",
                reaction_plan="",
            )
        )

    # 3. Alignment Gate
    if alignment_confidence < min_alignment:
        results.append(
            RuleResult(
                rule_id="GATE-ALIGNMENT",
                family="pre_gates",
                name="Homography Blueprint Alignment Gate",
                source_doc="Blueprint Jig Alignment Standard",
                severity="CRITICAL",
                status="FAIL",
                mandatory=True,
                expected=f"Alignment confidence >= {min_alignment:.2f}",
                actual=f"{alignment_confidence:.3f}",
                reason=f"Blueprint perspective alignment confidence ({alignment_confidence:.2f}) below threshold ({min_alignment:.2f}). Re-capture required.",
                reaction_plan=REACTION_PLAN_SEGREGATE,
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="GATE-ALIGNMENT",
                family="pre_gates",
                name="Homography Blueprint Alignment Gate",
                source_doc="Blueprint Jig Alignment Standard",
                severity="CRITICAL",
                status="PASS",
                mandatory=True,
                expected=f"Alignment confidence >= {min_alignment:.2f}",
                actual=f"{alignment_confidence:.3f}",
                reason=f"Blueprint homography alignment confidence ({alignment_confidence:.2f}) exceeds threshold.",
                reaction_plan="",
            )
        )

    # 4. Variant Gate
    if not variant_selected:
        results.append(
            RuleResult(
                rule_id="GATE-VARIANT",
                family="pre_gates",
                name="Harness Variant Selection Gate",
                source_doc="Engineering Part Configuration",
                severity="CRITICAL",
                status="FAIL",
                mandatory=True,
                expected="Valid harness variant selected (e.g. YH200502)",
                actual="None",
                reason="No product variant selected for rule application.",
                reaction_plan=REACTION_PLAN_SEGREGATE,
            )
        )
    else:
        results.append(
            RuleResult(
                rule_id="GATE-VARIANT",
                family="pre_gates",
                name="Harness Variant Selection Gate",
                source_doc="Engineering Part Configuration",
                severity="CRITICAL",
                status="PASS",
                mandatory=True,
                expected="Valid harness variant selected",
                actual=variant_selected,
                reason=f"Active variant '{variant_selected}' confirmed.",
                reaction_plan="",
            )
        )

    # 5. Segmentation Sanity Gate
    if occupied_percentage is not None:
        if occupied_percentage < 0.1:
            results.append(
                RuleResult(
                    rule_id="GATE-SEGMENTATION",
                    family="pre_gates",
                    name="Harness Segmentation Sanity Gate",
                    source_doc="OpenCV Segmentation Quality Standard",
                    severity="CRITICAL",
                    status="FAIL",
                    mandatory=True,
                    expected="Occupied foreground percentage >= 0.1%",
                    actual=f"{occupied_percentage:.3f}%",
                    reason="Harness workpiece not detected on inspection table (blank image or severe occlusion).",
                    reaction_plan=REACTION_PLAN_SEGREGATE,
                )
            )

    return results
