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


class HarnessSegmentationService:
    """Robust wire-harness segmentation pipeline for inspection workstations.

    Handles:
    - Dark corrugated tubes, black wires, and colored connectors
    - Thin white / light-grey wires and white wire labels via adaptive thresholding
    - Exclusion of yellow measuring tapes on inspection board borders
    - Exclusion of off-table floor / border regions
    - Morphological continuity bridging across tape labels
    """

    def __init__(
        self,
        *,
        minimum_component_area_ratio: float = 0.0002,
        closing_kernel_size: int = 7,
        closing_iterations: int = 2,
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

        # ── 1. Table background brightness estimation ──────────────────────────
        # Measure central region where inspection board is guaranteed to be present
        center_h_start, center_h_end = int(height * 0.25), int(height * 0.75)
        center_w_start, center_w_end = int(width * 0.25), int(width * 0.75)
        bg_median_gray = float(np.median(grayscale[center_h_start:center_h_end, center_w_start:center_w_end]))
        bg_is_light = bg_median_gray > 100.0

        # ── 2. Dual Thresholding: Otsu + Adaptive Threshold ────────────────────
        # Otsu captures dark corrugated tubing and dark wires.
        # Adaptive thresholding captures light-colored/white wires, connectors, and
        # white tape labels that would otherwise be lost into the light table.
        thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
        otsu_threshold, otsu_mask = cv2.threshold(blurred, 0, 255, thresh_type | cv2.THRESH_OTSU)

        adapt_mask = cv2.adaptiveThreshold(
            blurred,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            31,
            7,
        )
        raw_mask = cv2.bitwise_or(otsu_mask, adapt_mask)

        # ── 3. Exclude yellow measuring tape along board edge ──────────────────
        # Harness inspection boards commonly have a yellow measuring tape pasted
        # along the right side of the board.
        right_boundary = int(width * 0.70)
        hsv_right = cv2.cvtColor(image[:, right_boundary:], cv2.COLOR_BGR2HSV)
        yellow_tape = cv2.inRange(hsv_right, np.array([12, 45, 60]), np.array([42, 255, 255]))
        yellow_tape_dilated = cv2.dilate(
            yellow_tape, cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9)), iterations=2
        )
        raw_mask[:, right_boundary:][yellow_tape_dilated > 0] = 0

        # ── 4. Exclude off-table dark floor on edge margins ───────────────────
        # When camera framing captures room floor outside the white board, columns
        # near the image border have median brightness well below board background.
        for col in range(int(width * 0.12)):
            if np.median(grayscale[:, col]) < bg_median_gray * 0.60:
                raw_mask[:, col] = 0
            else:
                break

        for col in range(width - 1, int(width * 0.88), -1):
            if np.median(grayscale[:, col]) < bg_median_gray * 0.60:
                raw_mask[:, col] = 0
            else:
                break

        # Disconnect extreme 3px border frame
        pad = 3
        raw_mask[:pad, :] = 0
        raw_mask[-pad:, :] = 0
        raw_mask[:, :pad] = 0
        raw_mask[:, -pad:] = 0

        # ── 5. Morphological Closing to Bridge Wire Gaps & Labels ──────────────
        closing_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.closing_kernel_size, self.closing_kernel_size),
        )
        closed_mask = cv2.morphologyEx(
            raw_mask, cv2.MORPH_CLOSE, closing_kernel, iterations=self.closing_iterations
        )

        # ── 6. Connected Component Filtering: Preserve Harness Assembly ────────
        component_count, labels, statistics, centroids = cv2.connectedComponentsWithStats(
            closed_mask, connectivity=8
        )
        cleaned_mask = np.zeros_like(closed_mask)
        removed_component_count = 0
        excluded_border_count = 0

        if component_count > 1:
            max_area = float(np.max(statistics[1:, cv2.CC_STAT_AREA]))
            min_keep_area = max(800.0, max_area * 0.015)

            for label in range(1, component_count):
                area = float(statistics[label, cv2.CC_STAT_AREA])
                comp_x = int(statistics[label, cv2.CC_STAT_LEFT])
                comp_y = int(statistics[label, cv2.CC_STAT_TOP])
                comp_w = float(statistics[label, cv2.CC_STAT_WIDTH])
                comp_h = float(statistics[label, cv2.CC_STAT_HEIGHT])
                shorter = min(comp_w, comp_h)
                longer = max(comp_w, comp_h) + 1e-6
                aspect = shorter / longer

                touches_border = (
                    comp_x <= pad + 1
                    or comp_y <= pad + 1
                    or comp_x + comp_w >= width - pad - 1
                    or comp_y + comp_h >= height - pad - 1
                )

                # Filter out border artefacts (thin strips, table edges)
                is_border_strip = touches_border and (
                    aspect < 0.08
                    or (comp_h > 0.25 * height and comp_w < 0.15 * width)
                    or (comp_w > 0.25 * width and comp_h < 0.15 * height)
                )

                if is_border_strip:
                    excluded_border_count += 1
                    continue

                if area >= min_keep_area:
                    cleaned_mask[labels == label] = 255
                else:
                    removed_component_count += 1

        # Fallback if over-filtered
        if cv2.countNonZero(cleaned_mask) == 0 and cv2.countNonZero(closed_mask) > 0:
            cleaned_mask = closed_mask.copy()

        # ── 7. External Contours and Skeleton Representation ───────────────────
        contours, _ = cv2.findContours(
            cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        contour_thickness = max(2, int(round(max(width, height) / 350.0)))
        contour_image = image.copy()
        cv2.drawContours(contour_image, contours, -1, (0, 0, 255), contour_thickness, cv2.LINE_AA)

        skeleton = skeletonize(cleaned_mask > 0)
        skeleton_raw = np.zeros_like(cleaned_mask)
        skeleton_raw[skeleton] = 255

        skeleton_dilation = max(1, int(round(max(width, height) / 600.0)))
        if skeleton_dilation > 1:
            dilation_kernel = cv2.getStructuringElement(
                cv2.MORPH_RECT, (skeleton_dilation, skeleton_dilation)
            )
            skeleton_image = cv2.dilate(skeleton_raw, dilation_kernel, iterations=1)
        else:
            skeleton_image = skeleton_raw

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
            excluded_border_component_count=excluded_border_count,
            image_width=width,
            image_height=height,
        )
