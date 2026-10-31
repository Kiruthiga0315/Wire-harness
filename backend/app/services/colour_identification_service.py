"""Comprehensive Colour Identification and Verification Service.

Detects coloured tape (green, dark blue, gray) and wire insulation colours
(red, green, blue, yellow, black, white, gray, brown, orange, purple)
from wire harness inspection images using OpenCV HSV/LAB colour-space analysis.

Integrates with the existing harness graph for branch association and
with Golden Reference for verification.
"""

from __future__ import annotations

import base64
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from app.config.colour_thresholds import (
    ColourThreshold,
    HSVRange,
    TapeThresholds,
    WireThresholds,
    default_tape_colour_thresholds,
    default_tape_thresholds,
    default_wire_colour_thresholds,
    default_wire_thresholds,
)
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

VerificationStatus = Literal["PASS", "NG", "UNCERTAIN", "NOT_CONFIGURED"]


@dataclass
class DetectedRegion:
    """A single colour-detected region."""
    region_id: str
    region_type: Literal["tape", "wire"]
    detected_color: str
    bbox: tuple[int, int, int, int]  # x, y, w, h
    center: tuple[int, int]
    area: int
    width: int
    height: int
    confidence: float
    status: str  # DETECTED, IDENTIFIED, UNCERTAIN, NOT_DETECTED
    branch_id: str  # "unassigned" if no branch
    mean_hsv: tuple[float, float, float] | None = None
    mean_lab: tuple[float, float, float] | None = None
    contour: Any = field(default=None, repr=False)


@dataclass
class ColourSummary:
    green_tape: int = 0
    dark_blue_tape: int = 0
    gray_tape: int = 0
    wire_regions: int = 0
    uncertain_detections: int = 0


@dataclass
class VerificationResult:
    status: VerificationStatus
    message: str
    details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ColourIdentificationResult:
    """Complete result of colour identification on an image."""
    success: bool
    inspection_id: str
    image_width: int
    image_height: int
    colour_summary: ColourSummary
    tape_detections: list[DetectedRegion]
    wire_detections: list[DetectedRegion]
    verification: VerificationResult
    overlay_image: ImageArray | None = None
    original_image: ImageArray | None = None
    processing_time_ms: float = 0.0
    method: str = ""
    disclaimer: str = ""


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _png_data_url(image: ImageArray) -> str:
    """Encode a BGR image as a base64 PNG data URL."""
    ok, png = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("OpenCV could not encode image to PNG")
    return f"data:image/png;base64,{base64.b64encode(png.tobytes()).decode('ascii')}"


def _box_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
    """Intersection-over-union between two (x, y, w, h) boxes."""
    xa = max(a[0], b[0])
    ya = max(a[1], b[1])
    xb = min(a[0] + a[2], b[0] + b[2])
    yb = min(a[1] + a[3], b[1] + b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    area_a = a[2] * a[3]
    area_b = b[2] * b[3]
    return float(inter / (area_a + area_b - inter))


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------

class ColourIdentificationService:
    """Full-image colour identification for tape and wire insulation."""

    def __init__(
        self,
        *,
        segmentation_service: HarnessSegmentationService | None = None,
        tape_colour_thresholds: list[ColourThreshold] | None = None,
        wire_colour_thresholds: list[ColourThreshold] | None = None,
        tape_thresholds: TapeThresholds | None = None,
        wire_thresholds: WireThresholds | None = None,
    ) -> None:
        self.segmentation_service = segmentation_service or HarnessSegmentationService()
        self.tape_colour_thresholds = tape_colour_thresholds or default_tape_colour_thresholds()
        self.wire_colour_thresholds = wire_colour_thresholds or default_wire_colour_thresholds()
        self.tape_thresholds = tape_thresholds or default_tape_thresholds()
        self.wire_thresholds = wire_thresholds or default_wire_thresholds()

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def identify(
        self,
        image: ImageArray,
        *,
        inspection_id: str = "",
        harness_mask: ImageArray | None = None,
        skeleton: ImageArray | None = None,
        branch_data: list[dict[str, Any]] | None = None,
        node_data: list[dict[str, Any]] | None = None,
        golden_colour_config: dict[str, Any] | None = None,
    ) -> ColourIdentificationResult:
        """Run full colour identification pipeline on *image*.

        Parameters
        ----------
        image : BGR uint8 image
        inspection_id : Optional label
        harness_mask : Pre-computed binary mask (255 = harness)
        skeleton : Pre-computed skeleton image
        branch_data : Existing branch/node graph information
        node_data : Node (junction/terminal) coordinates
        golden_colour_config : Expected colour regions for verification
        """
        import time
        t0 = time.perf_counter()

        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a 3-channel BGR colour image")

        h_img, w_img = image.shape[:2]

        # 1. Preprocessing (preserves original BGR colour distribution)
        preprocessed = self._preprocess(image)

        # 2. Colour space conversions (done once on the preprocessed image)
        hsv = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(preprocessed, cv2.COLOR_BGR2LAB)

        # 3. Obtain harness mask & skeleton
        if harness_mask is None:
            harness_mask = self._compute_harness_mask(image, hsv)

        if skeleton is None:
            try:
                from skimage.morphology import skeletonize
                skeleton = (skeletonize(harness_mask > 0).astype(np.uint8)) * 255
            except Exception:
                skeleton = np.zeros_like(harness_mask)

        # 4. Detect tape regions
        tape_detections = self._detect_tape(
            image, hsv, lab, harness_mask, skeleton=skeleton,
        )

        # 5. Detect wire insulation colours (excluding already detected tape regions)
        wire_detections = self._detect_wire_colours(
            image, hsv, lab, harness_mask, skeleton=skeleton, tape_detections=tape_detections,
        )

        # Merge collinear/adjacent fragments of the same wire
        wire_detections = self._merge_wire_fragments(wire_detections)

        # Deduplication of wire detections via NMS and enclosure suppression
        wire_detections = self._remove_overlapping(wire_detections)

        # Cross-deduplication: If a wire detection overlaps significantly with a tape detection,
        # remove the wire detection (tape wrap takes priority over underlying wire)
        if tape_detections and wire_detections:
            filtered_wires: list[DetectedRegion] = []
            for wd in wire_detections:
                overlaps_tape = any(
                    _box_iou(wd.bbox, td.bbox) >= 0.35
                    for td in tape_detections
                )
                if not overlaps_tape:
                    filtered_wires.append(wd)
            wire_detections = filtered_wires

        # 6. Branch association
        if branch_data or node_data:
            self._associate_branches(
                tape_detections + wire_detections,
                branch_data or [],
                node_data or [],
                skeleton,
            )

        # 7. Golden Reference verification
        verification = self._verify_against_golden(
            tape_detections, wire_detections, golden_colour_config,
        )

        # 8. Build summary
        summary = ColourSummary(
            green_tape=sum(1 for d in tape_detections if d.detected_color == "green" and d.status in ("DETECTED", "IDENTIFIED")),
            dark_blue_tape=sum(1 for d in tape_detections if d.detected_color == "dark_blue" and d.status in ("DETECTED", "IDENTIFIED")),
            gray_tape=sum(1 for d in tape_detections if d.detected_color == "gray" and d.status in ("DETECTED", "IDENTIFIED")),
            wire_regions=sum(1 for d in wire_detections if d.status in ("IDENTIFIED", "DETECTED")),
            uncertain_detections=sum(
                1 for d in tape_detections + wire_detections if d.status == "UNCERTAIN"
            ),
        )

        # 9. Build overlay image
        overlay = self._create_overlay(
            image, tape_detections, wire_detections,
        )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return ColourIdentificationResult(
            success=True,
            inspection_id=inspection_id,
            image_width=w_img,
            image_height=h_img,
            colour_summary=summary,
            tape_detections=tape_detections,
            wire_detections=wire_detections,
            verification=verification,
            overlay_image=overlay,
            original_image=image,
            processing_time_ms=round(elapsed_ms, 1),
            method=(
                "HSV & LAB colour-space segmentation with morphological cleanup, "
                "shape-based tape vs wire classification, distance-transform wire isolation, "
                "and connected-component region extraction"
            ),
            disclaimer=(
                "Engineering colour identification output. Confidence scores reflect "
                "segmentation coverage and colour purity. Production use requires "
                "controlled illumination and calibrated camera colour profiles."
            ),
        )

    # -------------------------------------------------------------------
    # Preprocessing
    # -------------------------------------------------------------------

    def _preprocess(self, image: ImageArray) -> ImageArray:
        """Light preprocessing: subtle noise reduction without colour shifting.

        Preserves original BGR colour distribution without grey-world distortion.
        """
        return cv2.GaussianBlur(image, (3, 3), 0)

    # -------------------------------------------------------------------
    # Harness mask
    # -------------------------------------------------------------------

    def _compute_harness_mask(
        self, image: ImageArray, hsv: ImageArray,
    ) -> ImageArray:
        """Compute a foreground harness mask excluding the light inspection table."""
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Border sampling to detect background table level
        margin_y = max(3, int(h * 0.03))
        margin_x = max(4, int(w * 0.025))
        border = np.concatenate([
            gray[:margin_y, margin_x:-margin_x].ravel(),
            gray[-margin_y:, margin_x:-margin_x].ravel(),
            gray[margin_y:-margin_y, :margin_x].ravel(),
            gray[margin_y:-margin_y, -margin_x:].ravel(),
        ])
        bg_median = float(np.median(border))
        bg_is_light = bg_median > 130.0

        if bg_is_light:
            # Inspection table is bright and desaturated (low chroma)
            # Harness is darker than table (black conduit, dark connectors, shadows)
            # OR has distinct chromatic saturation (colored wires, blue/green tape)
            is_dark = blurred < min(160, int(bg_median - 25))
            is_chroma = (hsv[:, :, 1] > 38) & (hsv[:, :, 2] > 35) & (blurred < min(210, int(bg_median - 8)))
            foreground = (is_dark | is_chroma).astype(np.uint8) * 255
        else:
            foreground = (blurred > (bg_median + 25)).astype(np.uint8) * 255

        # Clean outer image margins
        b = 4
        foreground[:b, :] = 0
        foreground[-b:, :] = 0
        foreground[:, :b] = 0
        foreground[:, -b:] = 0

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(foreground, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Exclude small isolated table artifacts (< 70 px)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
        cleaned = np.zeros_like(mask)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= 70:
                cleaned[labels == i] = 255

        return cleaned

    # -------------------------------------------------------------------
    # Tape detection
    # -------------------------------------------------------------------

    def _detect_tape(
        self,
        image: ImageArray,
        hsv: ImageArray,
        lab: ImageArray,
        harness_mask: ImageArray,
        skeleton: ImageArray | None = None,
    ) -> list[DetectedRegion]:
        """Detect coloured tape regions strictly grounded in harness geometry."""
        detections: list[DetectedRegion] = []
        tape_idx = {"green_tape": 0, "dark_blue_tape": 0, "gray_tape": 0}

        skel_dist = None
        if skeleton is not None and np.count_nonzero(skeleton) > 0:
            skel_dist = cv2.distanceTransform(cv2.bitwise_not(skeleton), cv2.DIST_L2, 5)

        for threshold in self.tape_colour_thresholds:
            colour_mask = self._apply_colour_threshold(hsv, lab, threshold)

            # Restrict to harness region
            colour_mask = colour_mask & (harness_mask > 0)
            colour_mask_u8 = colour_mask.astype(np.uint8) * 255

            # Morphological cleanup
            k = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (threshold.morph_kernel_size, threshold.morph_kernel_size),
            )
            colour_mask_u8 = cv2.morphologyEx(colour_mask_u8, cv2.MORPH_OPEN, k)
            colour_mask_u8 = cv2.morphologyEx(colour_mask_u8, cv2.MORPH_CLOSE, k)

            contours, _ = cv2.findContours(
                colour_mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
            )

            for contour in contours:
                area = cv2.contourArea(contour)
                if area < self.tape_thresholds.min_area or area > self.tape_thresholds.max_area:
                    continue

                x, y, w, h = cv2.boundingRect(contour)

                # Skeleton proximity: tape must intersect harness skeleton / branches
                cx = x + w // 2
                cy = y + h // 2
                if skel_dist is not None:
                    # Tape wrap must be within 16px of skeleton
                    if skel_dist[cy, cx] > 16.0:
                        continue

                # Shape analysis for tape classification
                is_tape, tape_confidence = self._classify_as_tape(
                    contour, area, w, h, image, hsv, x, y,
                )
                if not is_tape:
                    continue

                # Compute mean colour and purity using local ROI
                roi_hsv = hsv[y:y+h, x:x+w]
                roi_lab = lab[y:y+h, x:x+w]
                roi_cmask = colour_mask_u8[y:y+h, x:x+w]

                shifted = contour - [x, y]
                roi_mask = np.zeros((h, w), dtype=np.uint8)
                cv2.drawContours(roi_mask, [shifted], -1, 255, -1)
                mask_pts = roi_mask > 0
                if not np.any(mask_pts):
                    continue

                mean_hsv = (
                    round(float(np.mean(roi_hsv[mask_pts, 0])), 1),
                    round(float(np.mean(roi_hsv[mask_pts, 1])), 1),
                    round(float(np.mean(roi_hsv[mask_pts, 2])), 1),
                )
                mean_lab = (
                    round(float(np.mean(roi_lab[mask_pts, 0])), 1),
                    round(float(np.mean(roi_lab[mask_pts, 1])), 1),
                    round(float(np.mean(roi_lab[mask_pts, 2])), 1),
                )

                reg_px = int(np.count_nonzero(mask_pts))
                col_px = int(np.count_nonzero(mask_pts & (roi_cmask > 0)))
                purity = col_px / max(1, reg_px)

                # Solidity
                hull = cv2.convexHull(contour)
                solidity = area / max(1, cv2.contourArea(hull))

                confidence = min(0.98, max(0.10, 0.45 * purity + 0.35 * tape_confidence + 0.20 * min(1.0, area / 400.0)))

                colour_name = threshold.colour_id.replace("_tape", "")
                status = "DETECTED" if confidence >= 0.60 else "UNCERTAIN"

                tape_idx[threshold.colour_id] = tape_idx.get(threshold.colour_id, 0) + 1
                idx = tape_idx[threshold.colour_id]

                detections.append(DetectedRegion(
                    region_id=f"T{idx:03d}",
                    region_type="tape",
                    detected_color=colour_name,
                    bbox=(x, y, w, h),
                    center=(cx, cy),
                    area=int(area),
                    width=w,
                    height=h,
                    confidence=round(confidence, 4),
                    status=status,
                    branch_id="unassigned",
                    mean_hsv=mean_hsv,
                    mean_lab=mean_lab,
                    contour=contour,
                ))

        # Remove overlapping tape detections
        detections = self._remove_overlapping(detections)
        return detections

    def _classify_as_tape(
        self,
        contour: Any,
        area: int,
        w: int,
        h: int,
        image: ImageArray,
        hsv: ImageArray,
        x: int,
        y: int,
    ) -> tuple[bool, float]:
        """Determine if a colour region is tape rather than wire insulation.

        Returns (is_tape, confidence).
        Uses shape analysis: tape is typically wider/flatter than wire cross-sections,
        has moderate aspect ratio, and occupies a compact band.
        """
        min_dim = min(w, h)
        max_dim = max(w, h)
        aspect = max_dim / max(1, min_dim)

        # Strict physical rejections:
        # 1. Thin wire runs (<8px) cannot be tape wraps
        if min_dim < 8:
            return False, 0.0
        # 2. Extreme aspect ratio (>10.0) cannot be tape wraps
        if aspect > 10.0:
            return False, 0.0
        # 3. Round / square mounting pegs (aspect < min_aspect_ratio) cannot be tape wraps
        if aspect < self.tape_thresholds.min_aspect_ratio:
            return False, 0.0
        # 4. Large background fixtures or board panels
        if max_dim > 350 or area > self.tape_thresholds.max_area:
            return False, 0.0

        confidence = 0.5

        # Solidity: filled area vs convex hull
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / max(1, hull_area)

        # Circularity
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * math.pi * area) / max(1, perimeter * perimeter)

        # Tape tends to be:
        # - Moderately elongated (aspect 1.2 - 8.0)
        # - High solidity (>0.4)
        # - Low circularity (<0.7)
        # - Area between 150 and 80000 px

        # Score each criterion
        if solidity >= self.tape_thresholds.min_solidity:
            confidence += 0.15
        if circularity <= self.tape_thresholds.max_circularity:
            confidence += 0.10
        if 1.0 <= aspect <= 12.0:
            confidence += 0.10

        # Tape regions are typically larger than individual wire pixels
        if area >= 300:
            confidence += 0.10

        # Check that the region is compact (not a thin scattered wire)
        bbox_area = w * h
        fill_ratio = area / max(1, bbox_area)
        if fill_ratio >= 0.25:
            confidence += 0.05

        # Cap confidence
        confidence = min(0.98, confidence)

        # Require minimum confidence to classify as tape
        is_tape = confidence >= 0.45 and solidity >= 0.20

        return is_tape, confidence

    # -------------------------------------------------------------------
    # Wire insulation colour detection
    # -------------------------------------------------------------------

    def _detect_wire_colours(
        self,
        image: ImageArray,
        hsv: ImageArray,
        lab: ImageArray,
        harness_mask: ImageArray,
        skeleton: ImageArray | None = None,
        tape_detections: list[DetectedRegion] | None = None,
    ) -> list[DetectedRegion]:
        """Detect wire insulation colours grounded in skeleton and wire geometry."""
        detections: list[DetectedRegion] = []

        # Build tape exclusion mask so detected tape wraps cannot produce wire false-positives
        tape_mask = np.zeros(harness_mask.shape, dtype=bool)
        if tape_detections:
            for td in tape_detections:
                tx, ty, tw, th = td.bbox
                tape_mask[ty : ty + th, tx : tx + tw] = True

        # Distance transform from skeleton to restrict candidate search to actual branch corridors
        skel_dist = None
        if skeleton is not None and np.count_nonzero(skeleton) > 0:
            skel_dist = cv2.distanceTransform(cv2.bitwise_not(skeleton), cv2.DIST_L2, 5)

        wire_mask = (harness_mask == 255) & ~tape_mask
        if skel_dist is not None:
            # Wire runs must lie within 22px corridor of skeleton branches
            wire_mask = wire_mask & (skel_dist <= 22.0)

        # Exclude specular highlights (high brightness, very low saturation glare)
        v_chan = hsv[:, :, 2].astype(int)
        s_chan = hsv[:, :, 1].astype(int)
        specular = (v_chan > 225) & (s_chan < 25)
        wire_mask = wire_mask & ~specular

        wire_idx_counters: dict[str, int] = {}

        for threshold in self.wire_colour_thresholds:
            colour_mask = self._apply_colour_threshold(hsv, lab, threshold)

            # Restrict to wire corridor
            colour_on_wire = colour_mask & wire_mask
            colour_u8 = colour_on_wire.astype(np.uint8) * 255

            # Morphological cleanup
            k_size = max(3, threshold.morph_kernel_size - 2)
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size))
            colour_u8 = cv2.morphologyEx(colour_u8, cv2.MORPH_OPEN, k)

            # Connected components
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                colour_u8, connectivity=8,
            )

            for i in range(1, num_labels):
                area = int(stats[i, cv2.CC_STAT_AREA])
                x = int(stats[i, cv2.CC_STAT_LEFT])
                y = int(stats[i, cv2.CC_STAT_TOP])
                w = int(stats[i, cv2.CC_STAT_WIDTH])
                h = int(stats[i, cv2.CC_STAT_HEIGHT])
                cx = int(centroids[i][0])
                cy = int(centroids[i][1])

                min_dim = min(w, h)
                max_dim = max(w, h)
                aspect = max_dim / max(1, min_dim)

                # Area filter: small dust blobs rejected
                if area < self.wire_thresholds.min_area:
                    # Allow slightly smaller area if highly elongated (thin wire strand)
                    if not (area >= 40 and aspect >= 2.0):
                        continue

                # 1. Reject square/compact connector blocks and terminal housings
                if min_dim >= self.wire_thresholds.connector_min_dim and aspect < self.wire_thresholds.connector_max_aspect:
                    continue

                # 2. Reject thick conduit or board panels (wires have limited cross-section radius)
                if min_dim > int(self.wire_thresholds.max_wire_radius * 1.5):
                    continue

                # 3. Require elongated wire geometry
                if aspect < self.wire_thresholds.min_aspect_ratio:
                    continue

                # Fast local ROI extraction for mean colours
                labels_crop = labels[y : y + h, x : x + w]
                comp_mask_crop = labels_crop == i
                if not np.any(comp_mask_crop):
                    continue

                hsv_crop = hsv[y : y + h, x : x + w]
                lab_crop = lab[y : y + h, x : x + w]
                mean_hsv = (
                    round(float(np.mean(hsv_crop[comp_mask_crop, 0])), 1),
                    round(float(np.mean(hsv_crop[comp_mask_crop, 1])), 1),
                    round(float(np.mean(hsv_crop[comp_mask_crop, 2])), 1),
                )
                mean_lab = (
                    round(float(np.mean(lab_crop[comp_mask_crop, 0])), 1),
                    round(float(np.mean(lab_crop[comp_mask_crop, 1])), 1),
                    round(float(np.mean(lab_crop[comp_mask_crop, 2])), 1),
                )

                # Colour purity: what fraction of the local bounding box pixels match the component
                comp_px = int(np.count_nonzero(comp_mask_crop))
                purity = comp_px / float(max(1, w * h))

                # Multi-factor principled confidence scoring
                geom_score = min(1.0, aspect / 2.8)
                purity_score = min(1.0, purity * 1.4)
                if skel_dist is not None:
                    d_skel = skel_dist[cy, cx]
                    skel_score = 1.0 if d_skel <= 4.0 else max(0.2, 1.0 - (d_skel - 4.0) / 16.0)
                else:
                    skel_score = 0.85
                area_score = min(1.0, area / 250.0)

                confidence = round(min(0.98, max(0.15, 0.40 * purity_score + 0.30 * geom_score + 0.18 * skel_score + 0.12 * area_score)), 4)

                if threshold.colour_id not in wire_idx_counters:
                    wire_idx_counters[threshold.colour_id] = 0
                wire_idx_counters[threshold.colour_id] += 1

                # Confidence tier status: >=0.80 High (IDENTIFIED), 0.60-0.79 Medium (IDENTIFIED), <0.60 Uncertain
                status = "IDENTIFIED" if confidence >= self.wire_thresholds.medium_confidence_min else "UNCERTAIN"

                detections.append(DetectedRegion(
                    region_id=f"W{sum(wire_idx_counters.values()):03d}",
                    region_type="wire",
                    detected_color=threshold.colour_id,
                    bbox=(x, y, w, h),
                    center=(cx, cy),
                    area=area,
                    width=w,
                    height=h,
                    confidence=confidence,
                    status=status,
                    branch_id="unassigned",
                    mean_hsv=mean_hsv,
                    mean_lab=mean_lab,
                ))

        return detections

    # -------------------------------------------------------------------
    # Colour thresholding
    # -------------------------------------------------------------------

    @staticmethod
    def _apply_colour_threshold(
        hsv: ImageArray,
        lab: ImageArray,
        threshold: ColourThreshold,
    ) -> NDArray[np.bool_]:
        """Apply HSV (and optional LAB) threshold to get a boolean mask."""
        h = hsv[:, :, 0].astype(int)
        s = hsv[:, :, 1].astype(int)
        v = hsv[:, :, 2].astype(int)

        combined = np.zeros(h.shape, dtype=bool)

        for rng in threshold.hsv_ranges:
            match = (
                (h >= rng.h_min) & (h <= rng.h_max)
                & (s >= rng.s_min) & (s <= rng.s_max)
                & (v >= rng.v_min) & (v <= rng.v_max)
            )
            combined |= match

        # Optional LAB refinement
        if threshold.lab_range is not None:
            lr = threshold.lab_range
            l_ch = lab[:, :, 0].astype(int)
            a_ch = lab[:, :, 1].astype(int)
            b_ch = lab[:, :, 2].astype(int)
            lab_ok = (
                (l_ch >= lr.l_min) & (l_ch <= lr.l_max)
                & (a_ch >= lr.a_min) & (a_ch <= lr.a_max)
                & (b_ch >= lr.b_min) & (b_ch <= lr.b_max)
            )
            combined = combined & lab_ok

        return combined

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _mean_colour(
        colour_image: ImageArray, mask: ImageArray,
    ) -> tuple[float, float, float] | None:
        """Compute mean colour values within a mask."""
        if np.sum(mask > 0) == 0:
            return None
        c1 = float(np.mean(colour_image[mask > 0, 0]))
        c2 = float(np.mean(colour_image[mask > 0, 1]))
        c3 = float(np.mean(colour_image[mask > 0, 2]))
        return (round(c1, 1), round(c2, 1), round(c3, 1))

    @staticmethod
    def _compute_confidence(
        area: int,
        colour_mask: ImageArray,
        region_mask: ImageArray,
        shape_confidence: float,
    ) -> float:
        """Compute detection confidence from area, colour purity, and shape."""
        # Colour purity: what fraction of the region mask pixels match the colour mask
        region_pixels = int(np.sum(region_mask > 0))
        if region_pixels == 0:
            return 0.0
        colour_in_region = int(np.sum((region_mask > 0) & (colour_mask > 0)))
        purity = colour_in_region / region_pixels

        # Area factor: larger regions are more reliable
        area_factor = min(1.0, area / 500.0)

        # Weighted combination
        confidence = 0.4 * purity + 0.3 * shape_confidence + 0.3 * area_factor
        return min(0.98, max(0.05, confidence))

    @staticmethod
    def _merge_wire_fragments(
        wires: list[DetectedRegion], max_gap: int = 24,
    ) -> list[DetectedRegion]:
        """Merge fragmented detections belonging to the same physical wire."""
        if len(wires) <= 1:
            return wires

        merged: list[DetectedRegion] = []
        used: set[int] = set()

        for i, w1 in enumerate(wires):
            if i in used:
                continue
            cur_box = list(w1.bbox)
            cur_area = w1.area
            cur_conf = w1.confidence
            color = w1.detected_color
            branch = w1.branch_id
            mean_hsv = w1.mean_hsv
            mean_lab = w1.mean_lab

            for j in range(i + 1, len(wires)):
                if j in used or wires[j].detected_color != color:
                    continue
                w2 = wires[j]
                bx1, by1, bw1, bh1 = cur_box
                bx2, by2, bw2, bh2 = w2.bbox
                gap_x = max(0, max(bx1, bx2) - min(bx1 + bw1, bx2 + bw2))
                gap_y = max(0, max(by1, by2) - min(by1 + bh1, by2 + bh2))
                if gap_x <= max_gap and gap_y <= max_gap:
                    nx1 = min(bx1, bx2)
                    ny1 = min(by1, by2)
                    nx2 = max(bx1 + bw1, bx2 + bw2)
                    ny2 = max(by1 + bh1, by2 + bh2)
                    cur_box = [nx1, ny1, nx2 - nx1, ny2 - ny1]
                    cur_area += w2.area
                    cur_conf = max(cur_conf, w2.confidence)
                    if branch == "unassigned" and w2.branch_id != "unassigned":
                        branch = w2.branch_id
                    used.add(j)

            used.add(i)
            cx = cur_box[0] + cur_box[2] // 2
            cy = cur_box[1] + cur_box[3] // 2
            status = "IDENTIFIED" if cur_conf >= 0.60 else "UNCERTAIN"
            merged.append(DetectedRegion(
                region_id=w1.region_id,
                region_type="wire",
                detected_color=color,
                bbox=tuple(cur_box),
                center=(cx, cy),
                area=cur_area,
                width=cur_box[2],
                height=cur_box[3],
                confidence=round(cur_conf, 4),
                status=status,
                branch_id=branch,
                mean_hsv=mean_hsv,
                mean_lab=mean_lab,
            ))

        for idx, w in enumerate(merged, start=1):
            w.region_id = f"W{idx:03d}"

        return merged

    @staticmethod
    def _remove_overlapping(
        detections: list[DetectedRegion],
        iou_threshold: float = 0.35,
    ) -> list[DetectedRegion]:
        """Remove highly overlapping and near-duplicate detections, keeping higher confidence."""
        if len(detections) <= 1:
            return detections

        # Sort by confidence descending
        detections.sort(key=lambda d: d.confidence, reverse=True)
        kept: list[DetectedRegion] = []

        for det in detections:
            overlaps = False
            dx, dy, dw, dh = det.bbox
            dcx, dcy = det.center
            for existing in kept:
                ex, ey, ew, eh = existing.bbox
                ecx, ecy = existing.center
                if dx + dw < ex or ex + ew < dx or dy + dh < ey or ey + eh < dy:
                    continue
                iou = _box_iou(det.bbox, existing.bbox)
                if iou > iou_threshold:
                    overlaps = True
                    break
                # Enclosure check: if a box is largely inside an existing detection
                inter_w = max(0, min(dx + dw, ex + ew) - max(dx, ex))
                inter_h = max(0, min(dy + dh, ey + eh) - max(dy, ey))
                inter_area = inter_w * inter_h
                if inter_area > 0:
                    enclosure = inter_area / float(min(dw * dh, ew * eh))
                    if enclosure >= 0.50:
                        overlaps = True
                        break
                # Same colour & category center proximity suppression
                if (
                    det.region_type == existing.region_type
                    and det.detected_color == existing.detected_color
                ):
                    dist = math.hypot(dcx - ecx, dcy - ecy)
                    if dist < 22.0:
                        overlaps = True
                        break
            if not overlaps:
                kept.append(det)

        return kept

    # -------------------------------------------------------------------
    # Branch association
    # -------------------------------------------------------------------

    def _associate_branches(
        self,
        detections: list[DetectedRegion],
        branch_data: list[dict[str, Any]],
        node_data: list[dict[str, Any]],
        skeleton: ImageArray | None,
    ) -> None:
        """Associate detected colour regions with nearby branches/nodes.

        Modifies detections in-place.
        """
        if not branch_data and not node_data:
            return

        # Build a list of (branch_id, midpoint_x, midpoint_y) from branches
        branch_points: list[tuple[str, int, int]] = []
        for branch in branch_data:
            bid = branch.get("branch_id", "")
            src = branch.get("source_node_id", "")
            tgt = branch.get("target_node_id", "")
            # Use node_data to find midpoint
            src_pt = self._find_node_point(src, node_data)
            tgt_pt = self._find_node_point(tgt, node_data)
            if src_pt and tgt_pt:
                mx = (src_pt[0] + tgt_pt[0]) // 2
                my = (src_pt[1] + tgt_pt[1]) // 2
                branch_points.append((bid, mx, my))

        if not branch_points:
            return

        for det in detections:
            cx, cy = det.center
            best_dist = float("inf")
            best_bid = "unassigned"

            for bid, bx, by in branch_points:
                dist = math.sqrt((cx - bx) ** 2 + (cy - by) ** 2)
                if dist < best_dist:
                    best_dist = dist
                    best_bid = bid

            # Only associate if reasonably close (within 150 pixels)
            max_assoc_dist = 150.0
            if best_dist <= max_assoc_dist:
                det.branch_id = best_bid
            else:
                det.branch_id = "unassigned"

    @staticmethod
    def _find_node_point(
        node_id: str, node_data: list[dict[str, Any]],
    ) -> tuple[int, int] | None:
        """Find coordinates of a node by ID."""
        for node in node_data:
            if node.get("node_id") == node_id:
                return (node.get("x", 0), node.get("y", 0))
        return None

    # -------------------------------------------------------------------
    # Golden Reference verification
    # -------------------------------------------------------------------

    def _verify_against_golden(
        self,
        tape_detections: list[DetectedRegion],
        wire_detections: list[DetectedRegion],
        golden_config: dict[str, Any] | None,
    ) -> VerificationResult:
        """Compare detections against Golden Reference expected colours."""
        if golden_config is None or not golden_config:
            return VerificationResult(
                status="NOT_CONFIGURED",
                message=(
                    "No colour expectations configured in Golden Reference. "
                    "Configure expected colour regions to enable verification."
                ),
            )

        expected_colours = golden_config.get("expected_colours", [])
        if not expected_colours:
            return VerificationResult(
                status="NOT_CONFIGURED",
                message="Golden Reference has no expected colour regions configured.",
            )

        all_detections = tape_detections + wire_detections
        details: list[dict[str, Any]] = []
        overall_pass = True
        has_uncertain = False

        for expected in expected_colours:
            exp_colour = expected.get("colour", "").lower()
            exp_type = expected.get("type", "any")  # "tape" or "wire" or "any"
            exp_region = expected.get("region", None)  # optional bbox

            # Find matching detections
            matches = [
                d for d in all_detections
                if d.detected_color == exp_colour
                and (exp_type == "any" or d.region_type == exp_type)
            ]

            if matches:
                best = max(matches, key=lambda d: d.confidence)
                if best.confidence >= 0.50:
                    detail_status = "PASS"
                else:
                    detail_status = "UNCERTAIN"
                    has_uncertain = True
            else:
                detail_status = "NG"
                overall_pass = False

            details.append({
                "expected_colour": exp_colour,
                "expected_type": exp_type,
                "status": detail_status,
                "matched_regions": len(matches),
                "best_confidence": round(matches[0].confidence, 3) if matches else 0.0,
            })

        if not overall_pass:
            status: VerificationStatus = "NG"
            message = "One or more expected colours were not detected."
        elif has_uncertain:
            status = "UNCERTAIN"
            message = "All expected colours detected but some with low confidence."
        else:
            status = "PASS"
            message = "All expected colours verified successfully."

        return VerificationResult(status=status, message=message, details=details)

    # -------------------------------------------------------------------
    # Overlay generation
    # -------------------------------------------------------------------

    def _create_overlay(
        self,
        image: ImageArray,
        tape_detections: list[DetectedRegion],
        wire_detections: list[DetectedRegion],
    ) -> ImageArray:
        """Create clean annotated overlay image with readable labels and semi-transparent badges."""
        overlay = image.copy()
        h_img, w_img = image.shape[:2]

        # Transparent layer for label background pills
        pill_layer = overlay.copy()

        # Exact category colour mapping (BGR)
        palette: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
            # colour_id: (outline_bgr, text_bgr)
            "green_tape": ((0, 200, 0), (255, 255, 255)),
            "dark_blue_tape": ((200, 70, 0), (255, 255, 255)),
            "gray_tape": ((160, 160, 160), (20, 20, 20)),
            "red": ((0, 0, 220), (255, 255, 255)),
            "green": ((0, 180, 0), (255, 255, 255)),
            "blue": ((220, 90, 0), (255, 255, 255)),
            "yellow": ((0, 210, 220), (20, 20, 20)),
            "black": ((30, 30, 30), (240, 240, 240)),
            "white": ((240, 240, 240), (20, 20, 20)),
            "gray": ((150, 150, 150), (20, 20, 20)),
            "brown": ((30, 70, 150), (255, 255, 255)),
            "orange": ((0, 130, 240), (20, 20, 20)),
            "purple": ((180, 40, 160), (255, 255, 255)),
        }

        # Track placed label rectangles to avoid visual collision
        placed_labels: list[tuple[int, int, int, int]] = []

        # Only draw confident, non-uncertain detections on the raster overlay to prevent clutter
        valid_tapes = [d for d in tape_detections if d.status == "DETECTED" and d.confidence >= 0.60]
        valid_wires = [d for d in wire_detections if d.status == "IDENTIFIED" and d.confidence >= 0.60]

        # Draw wire bounding boxes first (thin 1.5px)
        for det in valid_wires:
            outline_bgr, text_bgr = palette.get(det.detected_color, ((0, 200, 0), (255, 255, 255)))
            x, y, w, h = det.bbox

            # Thin bounding box outline
            cv2.rectangle(overlay, (x, y), (x + w, y + h), outline_bgr, 1, cv2.LINE_AA)

            pct = int(round(det.confidence * 100))
            label = f"WIRE: {det.detected_color.upper()} | {pct}%"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)

            # Collision-aware label placement: preferred top, fallback bottom
            lx = max(2, min(x, w_img - tw - 6))
            ly_top = y - 4
            ly_bottom = y + h + th + 6

            # Check overlap with existing placed labels
            candidate_box = (lx, ly_top - th - 3, lx + tw + 6, ly_top + 2)
            collides = any(
                not (candidate_box[2] < pb[0] or candidate_box[0] > pb[2] or candidate_box[3] < pb[1] or candidate_box[1] > pb[3])
                for pb in placed_labels
            )

            if collides or (ly_top - th - 3 < 0):
                lx = max(2, min(x, w_img - tw - 6))
                ly = min(h_img - 2, ly_bottom)
                final_box = (lx, ly - th - 3, lx + tw + 6, ly + 2)
            else:
                ly = ly_top
                final_box = candidate_box

            placed_labels.append(final_box)

            # Localized alpha blending only within the label pill ROI (preserves pristine image everywhere else)
            x1, y1 = max(0, final_box[0]), max(0, final_box[1])
            x2, y2 = min(w_img, final_box[2]), min(h_img, final_box[3])
            if x2 > x1 and y2 > y1:
                roi = overlay[y1:y2, x1:x2]
                pill = np.full_like(roi, outline_bgr)
                overlay[y1:y2, x1:x2] = cv2.addWeighted(pill, 0.65, roi, 0.35, 0)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (40, 40, 40), 1)
                cv2.putText(overlay, label, (lx + 3, ly - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, text_bgr, 1, cv2.LINE_AA)

        # Draw tape bounding boxes (2px outline with high visibility)
        for det in valid_tapes:
            palette_key = f"{det.detected_color}_tape"
            outline_bgr, text_bgr = palette.get(palette_key, ((0, 220, 0), (255, 255, 255)))
            x, y, w, h = det.bbox

            # Clean 2px outline for tape wraps
            cv2.rectangle(overlay, (x, y), (x + w, y + h), outline_bgr, 2, cv2.LINE_AA)

            pct = int(round(det.confidence * 100))
            colour_disp = det.detected_color.replace("_", " ").upper()
            label = f"{colour_disp} TAPE | {pct}%"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.40, 1)

            lx = max(2, min(x, w_img - tw - 8))
            ly_top = y - 5
            ly_bottom = y + h + th + 8

            candidate_box = (lx, ly_top - th - 4, lx + tw + 8, ly_top + 2)
            collides = any(
                not (candidate_box[2] < pb[0] or candidate_box[0] > pb[2] or candidate_box[3] < pb[1] or candidate_box[1] > pb[3])
                for pb in placed_labels
            )

            if collides or (ly_top - th - 4 < 0):
                lx = max(2, min(x, w_img - tw - 8))
                ly = min(h_img - 2, ly_bottom)
                final_box = (lx, ly - th - 4, lx + tw + 8, ly + 2)
            else:
                ly = ly_top
                final_box = candidate_box

            placed_labels.append(final_box)

            # Localized alpha blending for tape label
            x1, y1 = max(0, final_box[0]), max(0, final_box[1])
            x2, y2 = min(w_img, final_box[2]), min(h_img, final_box[3])
            if x2 > x1 and y2 > y1:
                roi = overlay[y1:y2, x1:x2]
                pill = np.full_like(roi, outline_bgr)
                overlay[y1:y2, x1:x2] = cv2.addWeighted(pill, 0.70, roi, 0.30, 0)
                cv2.rectangle(overlay, (x1, y1), (x2, y2), (30, 30, 30), 1)
                cv2.putText(overlay, label, (lx + 4, ly - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.40, text_bgr, 1, cv2.LINE_AA)

        return overlay
