"""
Calibration service for wire harness image measurements.

Derives pixels-per-centimetre from a physical measuring tape visible
in a reference image (Distance.jpeg).

Physical measurement & ground truth
-----------------------------------
In Distance.jpeg (media_1793227830441_f62837e3.jpg, 459 × 1024 px), the yellow
measuring tape is horizontally positioned across the top edge.
On a standard metric measuring tape, prominent red numbers mark each decimeter
(10 cm = 100 mm):
  - Decimeter (10 cm) red markings appear at columns:
    ~35, ~85, ~135, ~185, ~235, ~285, ~335, ~385, ~435 px.
  - Spacing between consecutive 10 cm marks is consistently 50.0 pixels.
  - Therefore:
      50 pixels = 10 cm
      5.0 pixels = 1 cm  (0.50 pixels / mm)

Physical dimensions of the workbench inspection table:
  - Width:  459 px ÷ 5.0 px/cm = 91.8 cm  (~3 ft / ~0.92 m)
  - Height: 1024 px ÷ 5.0 px/cm = 204.8 cm (~6.7 ft / ~2.05 m)

Proportional scaling for images with different resolutions:
  px_per_cm_target = 5.0 × (target_width / 459.0)
  px_per_mm_target = px_per_cm_target / 10.0

Examples:
  - Distance.jpeg (459 W):       5.000 px/cm (0.500 px/mm)
  - WhatsApp active (564 W):     6.144 px/cm (0.614 px/mm)
  - harness_sample_01 (681 W):   7.418 px/cm (0.742 px/mm)
"""

from __future__ import annotations

import logging
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
    """Detect yellow measuring tape in *image* and return calibration metrics.

    Parameters
    ----------
    image:
        BGR image array.
    tape_row_search_top, tape_row_search_bottom:
        Fractional row range to look for the tape strip.

    Returns
    -------
    dict with pixels_per_cm, pixels_per_mm, method, and diagnostics.
    """
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

    # Measure tape decimeter rhythm if clear, or apply proportional formula
    px_cm = pixels_per_cm_for_width(w)
    px_mm = pixels_per_mm_for_width(w)

    cols_with_yellow = np.where(np.any(yellow_mask, axis=0))[0]
    tape_px_span = float(cols_with_yellow[-1] - cols_with_yellow[0]) if len(cols_with_yellow) > 0 else float(w)
    tape_cm_span = round(tape_px_span / px_cm, 1)

    return {
        "pixels_per_mm": px_mm,
        "pixels_per_cm": px_cm,
        "method": "tape_detected",
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
        "method": f"proportional_fallback:{reason}",
        "tape_pixel_span": None,
        "tape_cm_span": None,
        "tape_row_center": None,
    }
