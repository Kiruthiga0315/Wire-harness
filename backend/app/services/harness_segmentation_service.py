from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from skimage.morphology import skeletonize

ImageArray = NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class HarnessSegmentationResult:
    binary_mask: ImageArray
    contour_image: ImageArray
    skeleton_image: ImageArray
    occupied_percentage: float
    contour_count: int
    otsu_threshold: float
    removed_component_count: int
    excluded_border_component_count: int
    image_width: int
    image_height: int
    cropped_base_image: ImageArray | None = None


class HarnessSegmentationService:
    """Experimental dark-object segmentation for controlled feasibility testing.

    This OpenCV pipeline assumes a dark harness on a light inspection surface.
    """

    def __init__(
        self,
        *,
        minimum_component_area_ratio: float = 0.0001,
        closing_kernel_size: int = 5,
        closing_iterations: int = 1,
    ) -> None:
        if not 0 < minimum_component_area_ratio < 1:
            raise ValueError("minimum_component_area_ratio must be between 0 and 1")
        if closing_kernel_size < 3 or closing_kernel_size % 2 == 0:
            raise ValueError("closing_kernel_size must be an odd integer of at least 3")
        self.minimum_component_area_ratio = minimum_component_area_ratio
        self.closing_kernel_size = closing_kernel_size
        self.closing_iterations = closing_iterations

    def segment_file(self, image_path: Path) -> HarnessSegmentationResult:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Unable to decode image: {image_path.name}")
        return self.segment(image)

    def segment(self, image: ImageArray) -> HarnessSegmentationResult:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a BGR colour image with three channels")

        height, width = image.shape[:2]
        total_pixels = float(height * width)
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)

        # 1. Background brightness polarity detection from inset image borders
        # Inset samples avoid dark letterbox margins or phone scanner borders
        inset_y = max(4, int(height * 0.02))
        inset_x = max(6, int(width * 0.025))
        inset_border = np.concatenate((
            grayscale[inset_y, inset_x:-inset_x],
            grayscale[-inset_y, inset_x:-inset_x],
            grayscale[inset_y:-inset_y, inset_x],
            grayscale[inset_y:-inset_y, -inset_x],
        ))
        border_median_gray = float(np.median(inset_border))
        bg_is_light = border_median_gray > 127.0

        # Multi-scale detection: captures dark conduits, thin colored wires, and light gray connectors
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        otsu_threshold_val, gray_mask = cv2.threshold(
            blurred,
            0,
            255,
            thresh_type | cv2.THRESH_OTSU,
        )
        otsu_threshold = float(otsu_threshold_val)

        # Adaptive threshold for fine thin branches and low-contrast wire strands
        # Constant 12 prevents smooth table gradients or plastic sheet glare from triggering
        adapt_mask = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            25,
            12,
        )

        # Chromatic saturation threshold to capture vibrant colored wires (blue, yellow, green, red)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat_mask = (
            (hsv[:, :, 1] > 35) & (hsv[:, :, 2] > 40)
        ).astype(np.uint8) * 255

        # Combine multi-modal evidence
        raw_mask = cv2.bitwise_or(gray_mask, adapt_mask)
        raw_mask = cv2.bitwise_or(raw_mask, sat_mask)

        # Exclude top calibration measuring tape from the wire harness mask
        ruler_band = np.zeros((height, width), dtype=bool)
        ruler_max_y = int(height * 0.038)
        ruler_band[:ruler_max_y, :] = (
            (hsv[:ruler_max_y, :, 0] >= 15)
            & (hsv[:ruler_max_y, :, 0] <= 38)
            & (hsv[:ruler_max_y, :, 1] >= 55)
        )
        ruler_mask = cv2.dilate(
            ruler_band.astype(np.uint8) * 255,
            cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)),
        ) > 0
        raw_mask[ruler_mask] = 0
        raw_mask[: int(height * 0.012), :] = 0
        # Exclude letterbox padding on outer columns if present
        if width > 100:
            margin_w = max(3, int(width * 0.015))
            if np.mean(grayscale[:, :margin_w]) < 80:
                raw_mask[:, :margin_w] = 0
            if np.mean(grayscale[:, -margin_w:]) < 80:
                raw_mask[:, -margin_w:] = 0

        # Guard against inverse polarity runaway
        if float(cv2.countNonZero(raw_mask)) / total_pixels > 0.70:
            raw_mask = cv2.bitwise_not(raw_mask)

        closing_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.closing_kernel_size, self.closing_kernel_size),
        )
        closed_mask = cv2.morphologyEx(
            raw_mask,
            cv2.MORPH_OPEN,
            closing_kernel,
        )
        closed_mask = cv2.morphologyEx(
            closed_mask,
            cv2.MORPH_CLOSE,
            closing_kernel,
            iterations=self.closing_iterations,
        )

        cleaned_mask, removed_component_count, excluded_border_component_count = (
            self._remove_artifacts_and_borders(closed_mask, grayscale, hsv)
        )

        contours, _ = cv2.findContours(
            cleaned_mask,
            cv2.RETR_TREE,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        contour_image = image.copy()
        cv2.drawContours(contour_image, contours, -1, (0, 0, 255), 2, cv2.LINE_AA)

        skeleton = skeletonize(cleaned_mask > 0)
        skeleton_image = np.zeros_like(cleaned_mask)
        skeleton_image[skeleton] = 255

        occupied_pixels = int(cv2.countNonZero(cleaned_mask))
        occupied_percentage = round(occupied_pixels * 100.0 / total_pixels, 3)

        return HarnessSegmentationResult(
            binary_mask=cleaned_mask,
            contour_image=contour_image,
            skeleton_image=skeleton_image,
            occupied_percentage=occupied_percentage,
            contour_count=len(contours),
            otsu_threshold=round(float(otsu_threshold), 2),
            removed_component_count=removed_component_count,
            excluded_border_component_count=excluded_border_component_count,
            image_width=width,
            image_height=height,
            cropped_base_image=image.copy(),
        )

    @staticmethod
    def _remove_artifacts_and_borders(
        mask: ImageArray,
        grayscale: ImageArray,
        hsv: ImageArray,
    ) -> tuple[ImageArray, int, int]:
        """Eliminate non-wire table artifacts (glare, paper/plastic crease) and peripheral border shadow."""
        component_count, labels, statistics, _ = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if component_count <= 1:
            return mask.copy(), 0, 0

        height, width = mask.shape[:2]
        total_pixels = float(height * width)
        cleaned = np.zeros_like(mask)
        removed_small = 0
        excluded_artifacts = 0

        minimum_area = max(24, round(total_pixels * 0.00005))
        ruler_zone_h = int(height * 0.045)

        for label in range(1, component_count):
            area = int(statistics[label, cv2.CC_STAT_AREA])
            if area < minimum_area:
                removed_small += 1
                continue

            comp_y = int(statistics[label, cv2.CC_STAT_TOP])
            comp_h = int(statistics[label, cv2.CC_STAT_HEIGHT])
            comp_pixels = labels == label

            comp_gray_min = int(np.min(grayscale[comp_pixels]))
            comp_sat_max = int(np.max(hsv[:, :, 1][comp_pixels]))

            # 1. Reject non-wire table glare or clear plastic document sleeve crease
            has_wire_evidence = (comp_gray_min < 178) or (comp_sat_max > 32)
            if not has_wire_evidence:
                excluded_artifacts += 1
                continue

            # 2. Reject top-border corner shadow/clamp
            if comp_y == 0 and (comp_y + comp_h <= ruler_zone_h):
                excluded_artifacts += 1
                continue

            cleaned[comp_pixels] = 255

        return cleaned, removed_small, excluded_artifacts
