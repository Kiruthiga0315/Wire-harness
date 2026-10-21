from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from app.services.harness_segmentation_service import ImageArray

SupportedColour = Literal[
    "BLACK",
    "WHITE",
    "BLUE",
    "RED",
    "GREEN",
    "YELLOW",
    "ORANGE",
    "GREY",
]

SUPPORTED_COLOURS: tuple[SupportedColour, ...] = (
    "BLACK",
    "WHITE",
    "BLUE",
    "RED",
    "GREEN",
    "YELLOW",
    "ORANGE",
    "GREY",
)


@dataclass(frozen=True, slots=True)
class ExtractedROI:
    image: ImageArray
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ColorInspectionResult:
    expected_colour: SupportedColour
    detected_colour: SupportedColour
    mean_hsv: tuple[float, float, float]
    mean_lab: tuple[float, float, float]
    confidence: float
    status: Literal["PASS", "NG"]
    roi: ExtractedROI


class ColorInspectionService:
    """Initial deterministic colour feasibility service using OpenCV colour spaces.

    Thresholds are broad engineering defaults. Production use requires controlled
    illumination, camera colour calibration, reference samples, and model-wise limits.
    """

    def normalize_expected_colour(self, value: str) -> SupportedColour:
        normalized = value.strip().upper()
        if normalized == "GRAY":
            normalized = "GREY"
        if normalized not in SUPPORTED_COLOURS:
            raise ValueError(
                f"Unsupported expected colour '{value}'. Supported colours: "
                f"{', '.join(SUPPORTED_COLOURS)}"
            )
        return cast(SupportedColour, normalized)

    def extract_roi(
        self,
        image: ImageArray,
        *,
        center_x: int,
        center_y: int,
        width: int,
        height: int,
    ) -> ExtractedROI:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a BGR colour image with three channels")
        if width <= 0 or height <= 0:
            raise ValueError("ROI width and height must be positive")

        image_height, image_width = image.shape[:2]
        left = max(0, center_x - width // 2)
        top = max(0, center_y - height // 2)
        right = min(image_width, left + width)
        bottom = min(image_height, top + height)
        if left >= right or top >= bottom:
            raise ValueError("Checkpoint ROI lies outside the image")

        return ExtractedROI(
            image=image[top:bottom, left:right].copy(),
            x=left,
            y=top,
            width=right - left,
            height=bottom - top,
        )

    def inspect(
        self,
        image: ImageArray,
        *,
        expected_colour: str,
        center_x: int,
        center_y: int,
        roi_width: int,
        roi_height: int,
    ) -> ColorInspectionResult:
        expected = self.normalize_expected_colour(expected_colour)
        roi = self.extract_roi(
            image,
            center_x=center_x,
            center_y=center_y,
            width=roi_width,
            height=roi_height,
        )

        hsv = cv2.cvtColor(roi.image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(roi.image, cv2.COLOR_BGR2LAB)
        mean_hsv = tuple(round(float(value), 2) for value in cv2.mean(hsv)[:3])
        mean_lab = tuple(round(float(value), 2) for value in cv2.mean(lab)[:3])

        labels = self._classify_pixels(hsv)
        counts = np.bincount(labels.ravel(), minlength=len(SUPPORTED_COLOURS))
        dominant_index, confidence = self._estimate_dominant_colour(counts, labels.size)
        detected = SUPPORTED_COLOURS[dominant_index]

        return ColorInspectionResult(
            expected_colour=expected,
            detected_colour=detected,
            mean_hsv=cast(tuple[float, float, float], mean_hsv),
            mean_lab=cast(tuple[float, float, float], mean_lab),
            confidence=confidence,
            status="PASS" if detected == expected else "NG",
            roi=roi,
        )

    @staticmethod
    def _classify_pixels(hsv: ImageArray) -> ImageArray:
        hue = hsv[:, :, 0]
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]
        labels = np.full(hue.shape, SUPPORTED_COLOURS.index("GREY"), dtype=np.uint8)

        labels[value < 55] = SUPPORTED_COLOURS.index("BLACK")
        labels[(value >= 205) & (saturation < 45)] = SUPPORTED_COLOURS.index("WHITE")

        chromatic = (value >= 55) & (saturation >= 45)
        labels[chromatic & ((hue < 10) | (hue >= 170))] = SUPPORTED_COLOURS.index("RED")
        labels[chromatic & (hue >= 10) & (hue < 23)] = SUPPORTED_COLOURS.index("ORANGE")
        labels[chromatic & (hue >= 23) & (hue < 38)] = SUPPORTED_COLOURS.index("YELLOW")
        labels[chromatic & (hue >= 38) & (hue < 85)] = SUPPORTED_COLOURS.index("GREEN")
        labels[chromatic & (hue >= 85) & (hue < 135)] = SUPPORTED_COLOURS.index("BLUE")

        # Purple/magenta is outside this first supported label set; map it to RED.
        labels[chromatic & (hue >= 135) & (hue < 170)] = SUPPORTED_COLOURS.index("RED")
        return labels

    @staticmethod
    def _estimate_dominant_colour(counts: NDArray[np.int64], pixel_count: int) -> tuple[int, float]:
        """Prefer coherent chromatic foreground when a light board dominates the ROI."""
        chromatic_indices = np.array(
            [
                SUPPORTED_COLOURS.index("BLUE"),
                SUPPORTED_COLOURS.index("RED"),
                SUPPORTED_COLOURS.index("GREEN"),
                SUPPORTED_COLOURS.index("YELLOW"),
                SUPPORTED_COLOURS.index("ORANGE"),
            ]
        )
        chromatic_count = int(counts[chromatic_indices].sum())
        if chromatic_count >= max(20, round(pixel_count * 0.02)):
            dominant_index = int(chromatic_indices[np.argmax(counts[chromatic_indices])])
            purity = float(counts[dominant_index] / chromatic_count)
            coverage = min(1.0, chromatic_count / (pixel_count * 0.08))
            return dominant_index, round(float(np.sqrt(purity * coverage)), 4)

        black_index = SUPPORTED_COLOURS.index("BLACK")
        if counts[black_index] >= max(20, round(pixel_count * 0.03)):
            coverage = min(1.0, float(counts[black_index] / (pixel_count * 0.20)))
            return black_index, round(0.55 + 0.45 * coverage, 4)

        dominant_index = int(np.argmax(counts))
        return dominant_index, round(float(counts[dominant_index] / pixel_count), 4)
