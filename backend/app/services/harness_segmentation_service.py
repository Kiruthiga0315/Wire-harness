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
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(grayscale, (5, 5), 0)

        otsu_threshold, dark_object_mask = cv2.threshold(
            blurred,
            0,
            255,
            cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU,
        )

        closing_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (self.closing_kernel_size, self.closing_kernel_size),
        )
        closed_mask = cv2.morphologyEx(
            dark_object_mask,
            cv2.MORPH_CLOSE,
            closing_kernel,
            iterations=self.closing_iterations,
        )

        cleaned_mask, removed_component_count = self._remove_small_components(closed_mask)
        cleaned_mask, excluded_border_component_count = self._remove_border_components(cleaned_mask)
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
        occupied_percentage = round(occupied_pixels * 100.0 / (width * height), 3)

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
        """Reject threshold regions connected to the frame edge as capture artifacts."""
        component_count, labels = cv2.connectedComponents(mask, connectivity=8)
        if component_count <= 1:
            return mask.copy(), 0

        border_labels = np.unique(
            np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
        )
        border_labels = border_labels[border_labels != 0]
        cleaned = mask.copy()
        for label in border_labels:
            cleaned[labels == label] = 0
        return cleaned, int(border_labels.size)
