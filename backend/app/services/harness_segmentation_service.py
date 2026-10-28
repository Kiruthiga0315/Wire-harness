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

    This OpenCV pipeline is deliberately simple. It assumes a dark harness on a
    light inspection surface and is not suitable as a production segmentation
    algorithm without calibration, lighting control, validation, and model-wise
    tuning.
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

        # Check if this is a wide camera view containing a white inspection table
        table_box = None
        if width > 1200:
            _, bright = cv2.threshold(blurred, 205, 255, cv2.THRESH_BINARY)
            kernel_table = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 25))
            table_closed = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, kernel_table)
            cnts, _ = cv2.findContours(table_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            max_area = 0.0
            for c in cnts:
                area = float(cv2.contourArea(c))
                if area > (total_pixels * 0.05):
                    bx, by, bw, bh = cv2.boundingRect(c)
                    if area > max_area:
                        max_area = area
                        table_box = (bx, by, bw, bh)

        if table_box is not None:
            tx, ty, tw, th = table_box
            pad_x, pad_y = int(tw * 0.02), int(th * 0.02)
            tx1 = max(0, tx + pad_x)
            ty1 = max(0, ty + pad_y)
            tx2 = min(width, tx + tw - pad_x)
            ty2 = min(height, ty + th - pad_y)

            # Crop to the table ONLY: remove outside floor, room, people, and chairs
            image = image[ty1:ty2, tx1:tx2]
            height, width = image.shape[:2]
            total_pixels = float(height * width)
            grayscale = grayscale[ty1:ty2, tx1:tx2]
            blurred = blurred[ty1:ty2, tx1:tx2]

            otsu_threshold_val, raw_mask = cv2.threshold(
                blurred,
                0,
                255,
                cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
            )
            otsu_threshold = float(otsu_threshold_val)

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
        else:
            # 1. Background brightness polarity detection from image borders
            border_gray = np.concatenate((
                grayscale[0, :], grayscale[-1, :], grayscale[:, 0], grayscale[:, -1]
            ))
            border_median_gray = float(np.median(border_gray))
            bg_is_light = border_median_gray > 127.0

            # Otsu threshold on grayscale with polarity adaptation
            thresh_type = cv2.THRESH_BINARY_INV if bg_is_light else cv2.THRESH_BINARY
            otsu_threshold_val, gray_mask = cv2.threshold(
                blurred,
                0,
                255,
                thresh_type | cv2.THRESH_OTSU,
            )
            otsu_threshold = float(otsu_threshold_val)

            # 2. Chromatic distance against median border background color
            # Captures coloured wires (yellow, red, blue, green) that match grayscale background intensity
            border_bgr = np.concatenate((
                image[0, :, :], image[-1, :, :], image[:, 0, :], image[:, -1, :]
            ), axis=0)
            bg_color_bgr = np.median(border_bgr, axis=0).astype(np.float32)
            diff = np.linalg.norm(image.astype(np.float32) - bg_color_bgr, axis=2).astype(np.uint8)
            diff_blurred = cv2.GaussianBlur(diff, (5, 5), 0)
            _, color_diff_mask = cv2.threshold(
                diff_blurred,
                0,
                255,
                cv2.THRESH_BINARY | cv2.THRESH_OTSU,
            )

            # Combine intensity difference and chromatic difference
            diff_ratio = float(cv2.countNonZero(color_diff_mask)) / total_pixels
            gray_ratio = float(cv2.countNonZero(gray_mask)) / total_pixels

            if 0.001 <= diff_ratio <= 0.60 and 0.001 <= gray_ratio <= 0.60:
                raw_mask = cv2.bitwise_or(gray_mask, color_diff_mask)
            elif 0.001 <= diff_ratio <= 0.60:
                raw_mask = color_diff_mask
            else:
                raw_mask = gray_mask

            # Guard against inverse polarity runaway
            if float(cv2.countNonZero(raw_mask)) / total_pixels > 0.70:
                raw_mask = cv2.bitwise_not(raw_mask)

            closing_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (self.closing_kernel_size, self.closing_kernel_size),
            )
            closed_mask = cv2.morphologyEx(
                raw_mask,
                cv2.MORPH_CLOSE,
                closing_kernel,
                iterations=self.closing_iterations,
            )

        cleaned_mask, removed_component_count = self._remove_small_components(closed_mask)
        cleaned_mask, excluded_border_component_count = self._remove_border_components(cleaned_mask)

        # If strict border filtering excluded everything, recover from closed_mask without border rejection
        if cv2.countNonZero(cleaned_mask) == 0 and cv2.countNonZero(closed_mask) > 0:
            cleaned_mask, removed_component_count = self._remove_small_components(closed_mask)
            excluded_border_component_count = 0

        contours, _ = cv2.findContours(
            cleaned_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        contour_image = image.copy()
        cv2.drawContours(contour_image, contours, -1, (0, 0, 255), 3, cv2.LINE_AA)

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

    def _remove_small_components(self, mask: ImageArray) -> tuple[ImageArray, int]:
        component_count, labels, statistics, _ = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        minimum_area = max(64, round(mask.size * self.minimum_component_area_ratio))
        cleaned = np.zeros_like(mask)
        removed_count = 0

        for label in range(1, component_count):
            area = int(statistics[label, cv2.CC_STAT_AREA])
            if area >= minimum_area:
                cleaned[labels == label] = 255
            else:
                removed_count += 1

        return cleaned, removed_count

    @staticmethod
    def _remove_border_components(mask: ImageArray) -> tuple[ImageArray, int]:
        """Reject peripheral border capture artifacts while preserving spanning workpieces."""
        component_count, labels, statistics, centroids = cv2.connectedComponentsWithStats(
            mask,
            connectivity=8,
        )
        if component_count <= 1:
            return mask.copy(), 0

        height, width = mask.shape[:2]
        total_pixels = float(height * width)

        border_labels = np.unique(
            np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
        )
        border_labels = border_labels[border_labels != 0]

        cleaned = mask.copy()
        excluded_count = 0

        for label in border_labels:
            area = float(statistics[label, cv2.CC_STAT_AREA])
            comp_w = float(statistics[label, cv2.CC_STAT_WIDTH])
            comp_h = float(statistics[label, cv2.CC_STAT_HEIGHT])
            cx, cy = centroids[label]

            # A genuine harness workpiece that touches or reaches near the edge
            # spans a large fraction of the frame and has its center of mass inside.
            is_spanning_workpiece = (
                (comp_w >= 0.30 * width and comp_h >= 0.30 * height)
                or (area >= 0.04 * total_pixels)
            )
            is_central = (0.08 * width <= cx <= 0.92 * width) and (
                0.08 * height <= cy <= 0.92 * height
            )

            if is_spanning_workpiece and is_central:
                continue

            cleaned[labels == label] = 0
            excluded_count += 1

        return cleaned, excluded_count
