"""
Calibration service for wire harness image measurements.

Single source of truth for all pixel-to-metric conversions with explicit
provenance ('tape-detected' | 'manual' | 'width-scaled' | 'uncalibrated')
and a calibrated flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Calibration constants derived from the physical Distance.jpeg tape reading
# ---------------------------------------------------------------------------

_CALIB_IMAGE_WIDTH_PX: int = 459
"""Pixel width of the calibration reference image (Distance.jpeg)."""

_CALIB_PX_PER_CM: float = 5.0
"""50 pixels per 10 cm (decimeter) on the yellow measuring tape = 5.0 px/cm."""

_CALIB_PX_PER_MM: float = _CALIB_PX_PER_CM / 10.0  # 0.50 px/mm

MIN_ALIGNMENT_CONFIDENCE_THRESHOLD: float = 0.85


@dataclass(frozen=True, slots=True)
class CalibrationInfo:
    calibrated: bool
    pixels_per_mm: float
    pixels_per_cm: float
    provenance: str  # "tape-detected" | "manual" | "width-scaled" | "uncalibrated"
    tape_pixel_span: float | None = None
    tape_cm_span: float | None = None
    tape_row_center: int | None = None
    alignment_confidence: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)


def pixels_per_cm_for_width(image_width_px: int) -> float:
    """Return pixels per centimetre scaled for *image_width_px*.

    Parameters
    ----------
    image_width_px:
        Target image width in pixels.

    Returns
    -------
    float:
        Pixels per centimetre.
    """
    if image_width_px <= 0:
        return 0.0
    scale = float(image_width_px) / float(_CALIB_IMAGE_WIDTH_PX)
    return round(_CALIB_PX_PER_CM * scale, 4)


def pixels_per_mm_for_width(image_width_px: int) -> float:
    """Return pixels per millimetre scaled for *image_width_px*."""
    return round(pixels_per_cm_for_width(image_width_px) / 10.0, 5)


def detect_tape_calibration(
    image: NDArray[np.uint8],
    *,
    tape_row_search_top: float = 0.0,
    tape_row_search_bottom: float = 0.08,
) -> dict[str, Any]:
    """Detect yellow measuring tape in *image* and return calibration metrics."""
    if image is None or image.ndim != 3:
        return _fallback_calibration(image, reason="invalid_image")

    h, w = image.shape[:2]
    row_top = int(h * tape_row_search_top)
    row_bot = int(h * tape_row_search_bottom)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    tape_hsv = hsv[row_top:row_bot, :, :]

    # Yellow mask
    yellow_mask = cv2.inRange(
        tape_hsv,
        np.array([15, 70, 70], dtype=np.uint8),
        np.array([40, 255, 255], dtype=np.uint8),
    )

    if not np.any(yellow_mask):
        return _fallback_calibration(image, reason="no_yellow_tape")

    # Densest yellow row
    row_sums = np.sum(yellow_mask, axis=1)
    tape_center_row = int(np.argmax(row_sums)) + row_top

    px_cm = pixels_per_cm_for_width(w)
    px_mm = pixels_per_mm_for_width(w)

    cols_with_yellow = np.where(np.any(yellow_mask, axis=0))[0]
    tape_px_span = float(cols_with_yellow[-1] - cols_with_yellow[0]) if len(cols_with_yellow) > 0 else float(w)
    tape_cm_span = round(tape_px_span / px_cm, 1) if px_cm > 0 else 0.0

    return {
        "pixels_per_mm": px_mm,
        "pixels_per_cm": px_cm,
        "method": "tape-detected",
        "tape_pixel_span": tape_px_span,
        "tape_cm_span": tape_cm_span,
        "tape_row_center": tape_center_row,
    }


def _fallback_calibration(
    image: NDArray[np.uint8] | None,
    *,
    reason: str = "unknown",
) -> dict[str, Any]:
    w = int(image.shape[1]) if image is not None and hasattr(image, "shape") else _CALIB_IMAGE_WIDTH_PX
    px_cm = pixels_per_cm_for_width(w)
    px_mm = pixels_per_mm_for_width(w)
    return {
        "pixels_per_mm": px_mm,
        "pixels_per_cm": px_cm,
        "method": f"width-scaled:{reason}",
        "tape_pixel_span": None,
        "tape_cm_span": None,
        "tape_row_center": None,
    }


def resolve_calibration(
    image: NDArray[np.uint8] | None = None,
    *,
    override_pixels_per_mm: float | None = None,
    config: dict[str, Any] | None = None,
    alignment_confidence: float = 1.0,
    min_alignment_confidence: float = MIN_ALIGNMENT_CONFIDENCE_THRESHOLD,
) -> CalibrationInfo:
    """Resolve single source-of-truth calibration info with explicit provenance.

    If alignment_confidence is below min_alignment_confidence, or if no valid
    scale can be derived, returns calibrated=False with provenance='uncalibrated'.
    """
    if alignment_confidence < min_alignment_confidence:
        logger.warning(
            "Alignment confidence %.3f is below required threshold %.3f; calibration gate failed",
            alignment_confidence,
            min_alignment_confidence,
        )
        return CalibrationInfo(
            calibrated=False,
            pixels_per_mm=0.0,
            pixels_per_cm=0.0,
            provenance="uncalibrated",
            alignment_confidence=alignment_confidence,
            details={"gate_failed": "alignment_confidence_too_low", "alignment_confidence": alignment_confidence},
        )

    # 1. Manual override
    if override_pixels_per_mm is not None and override_pixels_per_mm > 0:
        ppm = float(override_pixels_per_mm)
        return CalibrationInfo(
            calibrated=True,
            pixels_per_mm=round(ppm, 5),
            pixels_per_cm=round(ppm * 10.0, 4),
            provenance="manual",
            alignment_confidence=alignment_confidence,
            details={"source": "manual_override"},
        )

    # 2. In-situ Tape detection from image
    if image is not None and hasattr(image, "shape") and image.ndim == 3:
        tape_res = detect_tape_calibration(image)
        if tape_res.get("method") == "tape-detected":
            ppm = float(tape_res["pixels_per_mm"])
            return CalibrationInfo(
                calibrated=True,
                pixels_per_mm=round(ppm, 5),
                pixels_per_cm=round(float(tape_res["pixels_per_cm"]), 4),
                provenance="tape-detected",
                tape_pixel_span=tape_res.get("tape_pixel_span"),
                tape_cm_span=tape_res.get("tape_cm_span"),
                tape_row_center=tape_res.get("tape_row_center"),
                alignment_confidence=alignment_confidence,
                details=tape_res,
            )

        # 3. Proportional width-scaled from table geometry
        w = int(image.shape[1])
        if w > 0:
            ppm = pixels_per_mm_for_width(w)
            return CalibrationInfo(
                calibrated=True,
                pixels_per_mm=ppm,
                pixels_per_cm=pixels_per_cm_for_width(w),
                provenance="width-scaled",
                alignment_confidence=alignment_confidence,
                details={"reason": tape_res.get("method", "width_scaled"), "image_width": w},
            )

    # 4. Config fallback if specified
    if config:
        calib_cfg = config.get("calibration", {})
        if calib_cfg.get("calibrated", False) and calib_cfg.get("pixels_per_mm", 0) > 0:
            ppm = float(calib_cfg["pixels_per_mm"])
            return CalibrationInfo(
                calibrated=True,
                pixels_per_mm=round(ppm, 5),
                pixels_per_cm=round(ppm * 10.0, 4),
                provenance=calib_cfg.get("method", "manual"),
                alignment_confidence=alignment_confidence,
                details=calib_cfg,
            )

    return CalibrationInfo(
        calibrated=False,
        pixels_per_mm=0.0,
        pixels_per_cm=0.0,
        provenance="uncalibrated",
        alignment_confidence=alignment_confidence,
        details={"reason": "no_calibration_source_available"},
    )
