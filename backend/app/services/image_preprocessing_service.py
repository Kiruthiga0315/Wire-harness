from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

ImageArray = NDArray[np.uint8]
QualityStatus = Literal["PASS", "REVIEW", "REJECT"]


@dataclass(frozen=True, slots=True)
class ImageQualityMetrics:
    blur_score: float
    brightness_mean: float
    contrast_rms: float
    is_blurry: bool
    is_underexposed: bool
    is_overexposed: bool
    is_low_contrast: bool
    quality_status: QualityStatus
    quality_notes: list[str]


@dataclass(frozen=True, slots=True)
class PreprocessingResult:
    original_image: ImageArray
    preprocessed_image: ImageArray
    original_dimensions: tuple[int, int]
    processed_dimensions: tuple[int, int]
    scale_factor: float
    padding: tuple[int, int, int, int]
    quality_metrics: ImageQualityMetrics
    rotation_applied_deg: int
    denoised: bool
    clahe_applied: bool


class ImagePreprocessingService:
    """Universal non-destructive image preprocessing for wire-harness inspection.

    Ensures format readability, EXIF orientation correction, dimensional preservation,
    rigorous quality assessment (blur, illumination, contrast), and gentle conditional
    enhancement without removing thin wire strands or connector details.
    """

    def __init__(
        self,
        *,
        blur_laplacian_threshold: float = 85.0,
        min_brightness: float = 35.0,
        max_brightness: float = 230.0,
        min_contrast_rms: float = 22.0,
        min_resolution: tuple[int, int] = (64, 64),
    ) -> None:
        self.blur_laplacian_threshold = blur_laplacian_threshold
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_contrast_rms = min_contrast_rms
        self.min_resolution = min_resolution

    def assess_quality(self, bgr_image: ImageArray) -> ImageQualityMetrics:
        """Evaluate blur, brightness, and contrast without altering the image."""
        if bgr_image.size == 0 or bgr_image.ndim != 3:
            return ImageQualityMetrics(
                blur_score=0.0,
                brightness_mean=0.0,
                contrast_rms=0.0,
                is_blurry=True,
                is_underexposed=True,
                is_overexposed=False,
                is_low_contrast=True,
                quality_status="REJECT",
                quality_notes=["Invalid or empty image array"],
            )

        gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)

        # 1. Blur via variance of Laplacian
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # 2. Brightness via luminance mean
        brightness_mean = float(np.mean(gray))

        # 3. RMS Contrast
        contrast_rms = float(np.std(gray))

        is_blurry = laplacian_var < self.blur_laplacian_threshold
        is_underexposed = brightness_mean < self.min_brightness
        is_overexposed = brightness_mean > self.max_brightness
        is_low_contrast = contrast_rms < self.min_contrast_rms

        notes: list[str] = []
        if is_blurry:
            notes.append(f"Image is blurry (Laplacian variance {laplacian_var:.1f} < {self.blur_laplacian_threshold:.1f})")
        if is_underexposed:
            notes.append(f"Image is underexposed (Luminance {brightness_mean:.1f} < {self.min_brightness:.1f})")
        if is_overexposed:
            notes.append(f"Image is overexposed (Luminance {brightness_mean:.1f} > {self.max_brightness:.1f})")
        if is_low_contrast:
            notes.append(f"Image has low contrast (RMS {contrast_rms:.1f} < {self.min_contrast_rms:.1f})")

        h, w = bgr_image.shape[:2]
        if w < self.min_resolution[0] or h < self.min_resolution[1]:
            notes.append(f"Resolution {w}x{h} is below minimum supported {self.min_resolution[0]}x{self.min_resolution[1]}")

        # Quality status determination
        if is_blurry and (is_underexposed or is_overexposed):
            quality_status: QualityStatus = "REJECT"
        elif is_blurry or is_underexposed or is_overexposed or is_low_contrast:
            quality_status = "REVIEW"
        else:
            quality_status = "PASS"

        return ImageQualityMetrics(
            blur_score=round(laplacian_var, 2),
            brightness_mean=round(brightness_mean, 2),
            contrast_rms=round(contrast_rms, 2),
            is_blurry=is_blurry,
            is_underexposed=is_underexposed,
            is_overexposed=is_overexposed,
            is_low_contrast=is_low_contrast,
            quality_status=quality_status,
            quality_notes=notes,
        )

    def preprocess(
        self,
        bgr_image: ImageArray,
        target_max_dim: int | None = None,
        apply_denoise: bool = True,
        apply_clahe: bool = True,
    ) -> PreprocessingResult:
        """Run complete automatic non-destructive preprocessing on an input image."""
        if bgr_image.ndim != 3 or bgr_image.shape[2] != 3:
            raise ValueError("Expected a 3-channel BGR image")

        orig_h, orig_w = bgr_image.shape[:2]
        if orig_w < self.min_resolution[0] or orig_h < self.min_resolution[1]:
            raise ValueError(
                f"Image dimensions ({orig_w}x{orig_h}) are below minimum supported resolution "
                f"({self.min_resolution[0]}x{self.min_resolution[1]})"
            )

        # 1. Orientation check: standard wire-harness layout is horizontal (width >= height)
        # If image is vertical (height > 1.35 * width), rotate 90 deg clockwise to normalize layout
        rotation_applied_deg = 0
        working_image = bgr_image.copy()
        if orig_h > int(orig_w * 1.35):
            working_image = cv2.rotate(working_image, cv2.ROTATE_90_CLOCKWISE)
            rotation_applied_deg = 90
            logger.info("Auto-corrected vertical harness orientation (rotated 90 deg clockwise)")

        # 2. Quality assessment
        quality = self.assess_quality(working_image)

        # 3. Letterbox / scaling if target_max_dim specified
        scale_factor = 1.0
        pad_top, pad_bottom, pad_left, pad_right = 0, 0, 0, 0
        h, w = working_image.shape[:2]

        if target_max_dim is not None and (w > target_max_dim or h > target_max_dim):
            scale_factor = target_max_dim / float(max(w, h))
            new_w = int(round(w * scale_factor))
            new_h = int(round(h * scale_factor))
            working_image = cv2.resize(working_image, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # 4. Conditional edge-preserving denoising
        # Bilateral filter smooths board grain while strictly preserving sharp wire boundaries
        denoised = False
        if apply_denoise and (quality.blur_score > 350.0 or quality.contrast_rms < 35.0):
            working_image = cv2.bilateralFilter(working_image, d=5, sigmaColor=35, sigmaSpace=35)
            denoised = True

        # 5. Conditional CLAHE illumination normalization
        # Applied only when lighting is non-uniform or contrast is low; preserves true colors
        clahe_applied = False
        if apply_clahe and (quality.is_low_contrast or quality.is_underexposed):
            lab = cv2.cvtColor(working_image, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_eq = clahe.apply(l_channel)
            lab_eq = cv2.merge((l_eq, a_channel, b_channel))
            working_image = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2BGR)
            clahe_applied = True

        final_h, final_w = working_image.shape[:2]

        return PreprocessingResult(
            original_image=bgr_image,
            preprocessed_image=working_image,
            original_dimensions=(orig_w, orig_h),
            processed_dimensions=(final_w, final_h),
            scale_factor=scale_factor,
            padding=(pad_top, pad_bottom, pad_left, pad_right),
            quality_metrics=quality,
            rotation_applied_deg=rotation_applied_deg,
            denoised=denoised,
            clahe_applied=clahe_applied,
        )


image_preprocessing_service = ImagePreprocessingService()
