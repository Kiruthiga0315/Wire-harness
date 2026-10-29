from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from app.schemas.color_inspection import ColourVector
from app.schemas.wire_color import (
    WireColorDetail,
    WireColorIdentificationResponse,
    WireSectionROI,
)
from app.services.harness_segmentation_service import HarnessSegmentationService, ImageArray


def _png_data_url(image: ImageArray) -> str:
    encoded, png = cv2.imencode(".png", image)
    if not encoded:
        raise RuntimeError("OpenCV could not encode image to PNG")
    payload = base64.b64encode(png.tobytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


@dataclass(frozen=True, slots=True)
class ColorExtractionResult:
    color_id: Literal["dark_blue", "grey", "black", "green"]
    name: str
    detected: bool
    status: Literal["Detected", "Uncertain", "Not detected"]
    pixel_count: int
    percentage: float
    confidence: float
    mean_hsv: ColourVector | None
    mean_lab: ColourVector | None
    regions_count: int
    overlay_color_bgr: tuple[int, int, int]
    overlay_color_hex: str
    mask: ImageArray
    description: str


def _box_iou(box_a: tuple[int, int, int, int], box_b: tuple[int, int, int, int]) -> float:
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[0] + box_a[2], box_b[0] + box_b[2])
    yb = min(box_a[1] + box_a[3], box_b[1] + box_b[3])
    inter_w = max(0, xb - xa)
    inter_h = max(0, yb - ya)
    inter_area = inter_w * inter_h
    if inter_area == 0:
        return 0.0
    area_a = box_a[2] * box_a[3]
    area_b = box_b[2] * box_b[3]
    return float(inter_area / (area_a + area_b - inter_area))


class WireColorIdentificationService:
    """Precise wire colour identification for Dark Blue, Grey, Black, and Green wires.

    Calibrated against automotive reference harness workpieces across different
    lighting conditions, backgrounds, and orientations.
    Excludes black protective tape, corrugated tubing, connector housings,
    shadows, and white table backgrounds.
    Produces high-fidelity image overlays directly on top of the original harness image.
    """

    def __init__(
        self,
        *,
        segmentation_service: HarnessSegmentationService | None = None,
        max_wire_radius: float = 6.2,
        min_pixels_dark_blue: int = 35,
        min_pixels_grey: int = 35,
        min_pixels_black: int = 35,
        min_pixels_green: int = 20,
    ) -> None:
        self.segmentation_service = segmentation_service or HarnessSegmentationService()
        self.max_wire_radius = max_wire_radius
        self.min_pixels_dark_blue = min_pixels_dark_blue
        self.min_pixels_grey = min_pixels_grey
        self.min_pixels_black = min_pixels_black
        self.min_pixels_green = min_pixels_green

    def identify_colors(
        self,
        image: ImageArray,
        source_filename: str = "active_image.jpeg",
        harness_mask: ImageArray | None = None,
    ) -> WireColorIdentificationResponse:
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("Expected a 3-channel BGR image")

        height, width = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

        # 1. Obtain harness segmentation mask if not provided
        if harness_mask is None:
            seg_result = self.segmentation_service.segment(image)
            harness_mask = seg_result.binary_mask

        # Robustness guard: check if harness_mask mistakenly captured the white table
        # (common when room borders have dark chairs/floor outside the table)
        table_pixels = (gray > 185) & (hsv[:, :, 1] < 45)
        mask_is_table = False
        if harness_mask is not None:
            harness_px = int(np.sum(harness_mask == 255))
            if harness_px > 0:
                table_share_in_mask = np.sum((harness_mask == 255) & table_pixels) / harness_px
                if harness_px / (width * height) > 0.45 or table_share_in_mask > 0.35:
                    mask_is_table = True

        if mask_is_table or harness_mask is None or np.sum(harness_mask == 255) == 0:
            # Recover true foreground harness on inspection table
            recovered = (~table_pixels & (gray < 192)).astype(np.uint8) * 255
            recovered[:8, :] = 0
            recovered[-8:, :] = 0
            recovered[:, :8] = 0
            recovered[:, -8:] = 0
            kernel_rec = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            harness_mask = cv2.morphologyEx(recovered, cv2.MORPH_OPEN, kernel_rec)

        total_harness_pixels = int(np.sum(harness_mask == 255))
        if total_harness_pixels == 0:
            return self._empty_response(image, source_filename, 0, 0, width, height)

        # 2. Distance transform to isolate thin wire strands from thick conduit/tape
        dist = cv2.distanceTransform(harness_mask, cv2.DIST_L2, 5)

        # Thick core: conduit tubing bodies, heavy tape wraps, and connector housings have dist >= 6.8 px
        thick_core = (dist >= 6.8).astype(np.uint8) * 255
        # Dilate thick core by 11 px to form envelope encompassing edges/falloffs of conduit and tape
        thick_envelope = cv2.dilate(thick_core, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)))

        b = image[:, :, 0].astype(int)
        g = image[:, :, 1].astype(int)
        r = image[:, :, 2].astype(int)
        h = hsv[:, :, 0].astype(int)
        s = hsv[:, :, 1].astype(int)
        v = hsv[:, :, 2].astype(int)
        L = lab[:, :, 0].astype(int)
        A = lab[:, :, 1].astype(int)
        B_lab = lab[:, :, 2].astype(int)

        # 3. Exclude non-wire surfaces:
        # a. Specular highlights and white reflections
        specular_mask = (v > 215) & (s < 35)
        # b. Boundary shadow bleed (border edge falloff)
        deep_shadow = (v < 16)

        # Base thin wire strand mask (dist <= 5.5 px, dist >= 0.8 px)
        wire_base_mask = (
            (harness_mask == 255)
            & (dist <= self.max_wire_radius)
            & (dist >= 0.8)
            & ~specular_mask
            & ~deep_shadow
        )

        # Neutral wire mask strictly excludes the thick conduit/tape envelope
        # so corrugated black tubing and tape perimeter cannot be classified as grey or black wires
        neutral_wire_base_mask = wire_base_mask & (thick_envelope == 0)

        analyzed_wire_pixels = int(np.sum(wire_base_mask))
        if analyzed_wire_pixels == 0:
            return self._empty_response(image, source_filename, total_harness_pixels, 0, width, height)

        # 4. Strict Colour Classification on visible wire surfaces:
        # --- DARK BLUE (Cyan/Blue overlay) ---
        dark_blue_raw = (
            wire_base_mask
            & (h >= 90)
            & (h <= 138)
            & (s >= 18)
            & (v >= 25)
            & (v <= 170)
            & (b > r + 5)
            & (b >= g)
            & (B_lab < 126)
        )

        # --- GREEN (Bright Green overlay) ---
        green_raw = (
            wire_base_mask
            & (h >= 34)
            & (h <= 90)
            & (s >= 15)
            & (v >= 24)
            & (v <= 175)
            & (g > r + 3)
            & (g >= b - 2)
            & (A < 126)
        )

        # --- GREY WIRE (Light Grey with dark border overlay) ---
        # Distinct from black wire: V in [65..180], L in [65..185]
        # Distinct from white background table: V <= 180, L <= 185
        # Neutral chromaticity: S <= 28, |B - R| <= 12, |G - R| <= 12
        # LAB balance: |A - 128| <= 9, |B - 128| <= 9
        # Strictly outside conduit/tape envelope
        grey_raw = (
            neutral_wire_base_mask
            & (v >= 65)
            & (v <= 180)
            & (s <= 28)
            & (L >= 65)
            & (L <= 185)
            & (np.abs(b - r) <= 12)
            & (np.abs(g - r) <= 12)
            & (np.abs(A - 128) <= 9)
            & (np.abs(B_lab - 128) <= 9)
            & ~dark_blue_raw
            & ~green_raw
        )

        # --- BLACK WIRE (Orange/Amber overlay) ---
        # Strictly thin wire conductor runs outside conduit/tape envelope
        # Low to medium-low brightness: 18 <= V <= 62, 18 <= L <= 64
        # Neutral chromaticity: S <= 35, |B - R| <= 8, |G - R| <= 8
        black_raw = (
            neutral_wire_base_mask
            & (v >= 18)
            & (v <= 62)
            & (s <= 35)
            & (L <= 64)
            & (np.abs(b - r) <= 8)
            & (np.abs(g - r) <= 8)
            & ~dark_blue_raw
            & ~green_raw
            & ~grey_raw
        )

        # 5. Morphological cleanup
        cleanup_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        dark_blue_mask = self._clean_mask(dark_blue_raw, cleanup_kernel, min_area=8)
        green_mask = self._clean_mask(green_raw, cleanup_kernel, min_area=6)
        grey_mask = self._clean_mask(grey_raw, cleanup_kernel, min_area=10)
        black_mask = self._clean_mask(black_raw, cleanup_kernel, min_area=8)

        # Mutually exclusive priority: Chromatic > Grey > Black
        grey_mask[dark_blue_mask > 0] = 0
        grey_mask[green_mask > 0] = 0
        black_mask[dark_blue_mask > 0] = 0
        black_mask[green_mask > 0] = 0
        black_mask[grey_mask > 0] = 0

        # 6. Evaluate each colour with confidence thresholds
        blue_detail = self._build_detail(
            color_id="dark_blue",
            name="Dark Blue",
            mask=dark_blue_mask,
            image=image,
            hsv=hsv,
            lab=lab,
            total_wire_pixels=analyzed_wire_pixels,
            min_pixels=self.min_pixels_dark_blue,
            overlay_bgr=(255, 140, 0),     # Vibrant Cyan / Blue
            overlay_hex="#00BFFF",
            description="Identified dark blue insulated wire conductor runs.",
        )

        grey_detail = self._build_detail(
            color_id="grey",
            name="Grey",
            mask=grey_mask,
            image=image,
            hsv=hsv,
            lab=lab,
            total_wire_pixels=analyzed_wire_pixels,
            min_pixels=self.min_pixels_grey,
            overlay_bgr=(215, 215, 215),   # Light Grey / Silver (with dark border)
            overlay_hex="#CBD5E0",
            description="Identified grey insulated wire conductors and breakout leads.",
        )

        black_detail = self._build_detail(
            color_id="black",
            name="Black",
            mask=black_mask,
            image=image,
            hsv=hsv,
            lab=lab,
            total_wire_pixels=analyzed_wire_pixels,
            min_pixels=self.min_pixels_black,
            overlay_bgr=(0, 165, 255),     # Radiant Amber / Orange (high contrast on dark harness)
            overlay_hex="#FFA500",
            description="Identified thin black wire runs (excluding thick corrugated conduit and tape).",
        )

        green_detail = self._build_detail(
            color_id="green",
            name="Green",
            mask=green_mask,
            image=image,
            hsv=hsv,
            lab=lab,
            total_wire_pixels=analyzed_wire_pixels,
            min_pixels=self.min_pixels_green,
            overlay_bgr=(50, 255, 50),     # Bright / Lime Green
            overlay_hex="#00E676",
            description="Identified green insulated wire sections and connector leads.",
        )

        # 7. Extract non-overlapping prominent interactive selection boxes
        sections = self._extract_non_overlapping_sections(
            image=image,
            hsv=hsv,
            lab=lab,
            details=[blue_detail, grey_detail, black_detail, green_detail],
            total_wire_pixels=analyzed_wire_pixels,
        )

        # 8. Generate clean annotated composite overlay (for "All wires" view)
        overlay_image = self._create_clean_overlay(
            image=image,
            blue_mask=blue_detail.mask,
            grey_mask=grey_detail.mask,
            black_mask=black_detail.mask,
            green_mask=green_detail.mask,
            blue_detected=blue_detail.detected,
            grey_detected=grey_detail.detected,
            black_detected=black_detail.detected,
            green_detected=green_detail.detected,
        )

        # 9. Generate individual colour overlays directly on the original photo
        # NEVER return a raw binary mask!
        color_masks = {
            "dark_blue": _png_data_url(
                self._create_single_color_overlay(
                    image, blue_detail.mask, (255, 140, 0), (255, 210, 60), is_grey=False
                )
            ),
            "grey": _png_data_url(
                self._create_single_color_overlay(
                    image, grey_detail.mask, (215, 215, 215), (245, 245, 245), is_grey=True
                )
            ),
            "black": _png_data_url(
                self._create_single_color_overlay(
                    image, black_detail.mask, (0, 165, 255), (0, 215, 255), is_grey=False
                )
            ),
            "green": _png_data_url(
                self._create_single_color_overlay(
                    image, green_detail.mask, (50, 255, 50), (100, 255, 100), is_grey=False
                )
            ),
        }

        colors = [
            WireColorDetail(
                color_id=d.color_id,
                name=d.name,
                status=d.status,
                detected=d.detected,
                pixel_count=d.pixel_count,
                percentage=d.percentage,
                confidence=d.confidence,
                mean_hsv=d.mean_hsv,
                mean_lab=d.mean_lab,
                regions_count=d.regions_count,
                overlay_color_hex=d.overlay_color_hex,
                description=d.description,
            )
            for d in (blue_detail, grey_detail, black_detail, green_detail)
        ]

        return WireColorIdentificationResponse(
            source_image=source_filename,
            image_width=width,
            image_height=height,
            analyzed_wire_pixels=analyzed_wire_pixels,
            total_harness_pixels=total_harness_pixels,
            colors=colors,
            sections=sections,
            overlay_image=_png_data_url(overlay_image),
            original_image=_png_data_url(image),
            color_masks=color_masks,
            production_ready=False,
            method=(
                "Calibrated HSV & LAB colour-space analysis with conduit-envelope exclusion "
                "distinguishing Dark Blue, Grey, Black, and Green on original harness workpiece"
            ),
            disclaimer=(
                "Engineering feasibility analysis only. Confidently identifies visible wire insulation surfaces. "
                "Concealed sections inside opaque protective tubing or deep shadows are treated as unidentifiable."
            ),
        )

    def _clean_mask(self, raw_mask: NDArray[np.bool_], kernel: ImageArray, min_area: int) -> ImageArray:
        uint_mask = (raw_mask.astype(np.uint8) * 255)
        opened = cv2.morphologyEx(uint_mask, cv2.MORPH_OPEN, kernel)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
        cleaned = np.zeros_like(opened)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                cleaned[labels == i] = 255
        return cleaned

    def _build_detail(
        self,
        color_id: Literal["dark_blue", "grey", "black", "green"],
        name: str,
        mask: ImageArray,
        image: ImageArray,
        hsv: ImageArray,
        lab: ImageArray,
        total_wire_pixels: int,
        min_pixels: int,
        overlay_bgr: tuple[int, int, int],
        overlay_hex: str,
        description: str,
    ) -> ColorExtractionResult:
        pixel_count = int(np.sum(mask == 255))
        percentage = round((pixel_count / max(1, total_wire_pixels)) * 100.0, 2)

        num_labels, _, _, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        regions_count = max(0, num_labels - 1)

        # Categorize status: Detected vs Uncertain vs Not detected
        uncertain_threshold = max(12, int(min_pixels * 0.35))
        if pixel_count >= min_pixels:
            is_detected = True
            status: Literal["Detected", "Uncertain", "Not detected"] = "Detected"
            coverage_ratio = min(1.0, pixel_count / (total_wire_pixels * 0.025))
            confidence = round(min(0.98, 0.74 + 0.24 * coverage_ratio), 2)
        elif pixel_count >= uncertain_threshold:
            is_detected = False
            status = "Uncertain"
            confidence = round(float(pixel_count / (min_pixels * 1.5)), 2)
        else:
            is_detected = False
            status = "Not detected"
            confidence = 0.0

        if pixel_count > 0:
            mean_h = float(np.mean(hsv[mask == 255, 0]))
            mean_s = float(np.mean(hsv[mask == 255, 1]))
            mean_v = float(np.mean(hsv[mask == 255, 2]))
            mean_l = float(np.mean(lab[mask == 255, 0]))
            mean_a = float(np.mean(lab[mask == 255, 1]))
            mean_b = float(np.mean(lab[mask == 255, 2]))
            mean_hsv_obj = ColourVector(
                channel_1=round(mean_h, 1),
                channel_2=round(mean_s, 1),
                channel_3=round(mean_v, 1),
            )
            mean_lab_obj = ColourVector(
                channel_1=round(mean_l, 1),
                channel_2=round(mean_a, 1),
                channel_3=round(mean_b, 1),
            )
        else:
            mean_hsv_obj = None
            mean_lab_obj = None

        return ColorExtractionResult(
            color_id=color_id,
            name=name,
            detected=is_detected,
            status=status,
            pixel_count=pixel_count,
            percentage=percentage,
            confidence=confidence,
            mean_hsv=mean_hsv_obj,
            mean_lab=mean_lab_obj,
            regions_count=regions_count if (is_detected or status == "Uncertain") else 0,
            overlay_color_bgr=overlay_bgr,
            overlay_color_hex=overlay_hex,
            mask=mask,
            description=description,
        )

    def _extract_non_overlapping_sections(
        self,
        image: ImageArray,
        hsv: ImageArray,
        lab: ImageArray,
        details: list[ColorExtractionResult],
        total_wire_pixels: int,
    ) -> list[WireSectionROI]:
        """Extract clearly positioned, prominent, non-overlapping wire sections."""
        all_candidates: list[dict] = []
        img_h, img_w = image.shape[:2]

        for detail in details:
            if not detail.detected and detail.status != "Uncertain":
                continue

            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
                detail.mask, connectivity=8
            )
            if num_labels <= 1:
                continue

            for i in range(1, num_labels):
                area = int(stats[i, cv2.CC_STAT_AREA])
                left = int(stats[i, cv2.CC_STAT_LEFT])
                top = int(stats[i, cv2.CC_STAT_TOP])
                width = int(stats[i, cv2.CC_STAT_WIDTH])
                height = int(stats[i, cv2.CC_STAT_HEIGHT])

                # Require minimum size (area >= 18 px) and avoid image borders
                if (
                    area >= 18
                    and max(width, height) >= 6
                    and left > 8
                    and top > 8
                    and (left + width) < (img_w - 8)
                    and (top + height) < (img_h - 8)
                ):
                    all_candidates.append({
                        "color_id": detail.color_id,
                        "color_name": detail.name,
                        "status": detail.status,
                        "overlay_color_bgr": detail.overlay_color_bgr,
                        "overlay_color_hex": detail.overlay_color_hex,
                        "area": area,
                        "box": (left, top, width, height),
                        "comp_idx": i,
                        "labels": labels,
                    })

        all_candidates.sort(key=lambda c: c["area"], reverse=True)

        chosen: list[dict] = []
        max_per_color: dict[str, int] = {"dark_blue": 4, "grey": 4, "black": 4, "green": 3}
        color_counts: dict[str, int] = {"dark_blue": 0, "grey": 0, "black": 0, "green": 0}

        for cand in all_candidates:
            cid = cand["color_id"]
            if color_counts[cid] >= max_per_color[cid]:
                continue

            box = cand["box"]
            overlaps = False
            for existing in chosen:
                ebox = existing["box"]
                if _box_iou(box, ebox) > 0.10:
                    overlaps = True
                    break
                center_x1 = box[0] + box[2] / 2
                center_y1 = box[1] + box[3] / 2
                center_x2 = ebox[0] + ebox[2] / 2
                center_y2 = ebox[1] + ebox[3] / 2
                dist_sq = (center_x1 - center_x2) ** 2 + (center_y1 - center_y2) ** 2
                if dist_sq < (26 ** 2):
                    overlaps = True
                    break

            if not overlaps:
                chosen.append(cand)
                color_counts[cid] += 1

        sections: list[WireSectionROI] = []
        sec_num: dict[str, int] = {"dark_blue": 1, "grey": 1, "black": 1, "green": 1}

        for cand in chosen:
            cid = cand["color_id"]
            cname = cand["color_name"]
            cstatus = cand["status"]
            area = cand["area"]
            left, top, width, height = cand["box"]
            labels = cand["labels"]
            comp_idx = cand["comp_idx"]
            idx = sec_num[cid]
            sec_num[cid] += 1

            pad_x = max(24, int(width * 0.45))
            pad_y = max(24, int(height * 0.45))

            crop_x1 = max(0, left - pad_x)
            crop_y1 = max(0, top - pad_y)
            crop_x2 = min(img_w, left + width + pad_x)
            crop_y2 = min(img_h, top + height + pad_y)

            cropped_bgr = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()
            cropped_mask = (labels[crop_y1:crop_y2, crop_x1:crop_x2] == comp_idx).astype(np.uint8) * 255

            annotated_crop = cropped_bgr.copy()
            tint_crop = cropped_bgr.copy()
            tint_crop[cropped_mask == 255] = cand["overlay_color_bgr"]
            annotated_crop = cv2.addWeighted(cropped_bgr, 0.35, tint_crop, 0.65, 0)

            contours, _ = cv2.findContours(cropped_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cid == "grey":
                # Grey wire has a dark outer border and light inner border
                cv2.drawContours(annotated_crop, contours, -1, (40, 40, 40), 2, cv2.LINE_AA)
                cv2.drawContours(annotated_crop, contours, -1, (245, 245, 245), 1, cv2.LINE_AA)
            else:
                cv2.drawContours(annotated_crop, contours, -1, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.drawContours(annotated_crop, contours, -1, cand["overlay_color_bgr"], 1, cv2.LINE_AA)

            crop_h, crop_w = annotated_crop.shape[:2]
            raw_crop_display = cropped_bgr.copy()
            if crop_w < 200 or crop_h < 200:
                scale = max(200 / max(1, crop_w), 200 / max(1, crop_h))
                new_w = min(420, int(crop_w * scale))
                new_h = min(420, int(crop_h * scale))
                annotated_crop = cv2.resize(annotated_crop, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                raw_crop_display = cv2.resize(raw_crop_display, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            comp_pixels_mask = (labels == comp_idx)
            c_mean_h = float(np.mean(hsv[comp_pixels_mask, 0]))
            c_mean_s = float(np.mean(hsv[comp_pixels_mask, 1]))
            c_mean_v = float(np.mean(hsv[comp_pixels_mask, 2]))
            c_mean_l = float(np.mean(lab[comp_pixels_mask, 0]))
            c_mean_a = float(np.mean(lab[comp_pixels_mask, 1]))
            c_mean_b = float(np.mean(lab[comp_pixels_mask, 2]))

            sec_percentage = round((area / max(1, total_wire_pixels)) * 100.0, 2)
            sec_confidence = round(min(0.98, 0.76 + 0.22 * min(1.0, area / 120.0)), 2)

            section_id = f"sec-{cid}-{idx}"
            sections.append(
                WireSectionROI(
                    section_id=section_id,
                    color_id=cid,
                    color_name=cname,
                    status=cstatus,
                    x=left,
                    y=top,
                    width=width,
                    height=height,
                    pixel_count=area,
                    percentage=sec_percentage,
                    confidence=sec_confidence,
                    mean_hsv=ColourVector(
                        channel_1=round(c_mean_h, 1),
                        channel_2=round(c_mean_s, 1),
                        channel_3=round(c_mean_v, 1),
                    ),
                    mean_lab=ColourVector(
                        channel_1=round(c_mean_l, 1),
                        channel_2=round(c_mean_a, 1),
                        channel_3=round(c_mean_b, 1),
                    ),
                    cropped_image=_png_data_url(annotated_crop),
                    original_crop=_png_data_url(raw_crop_display),
                    overlay_color_hex=cand["overlay_color_hex"],
                    description=f"{cname} wire section #{idx} at pixel coordinates ({left}, {top}) with {area} conductor pixels.",
                )
            )

        return sections

    def _create_clean_overlay(
        self,
        image: ImageArray,
        blue_mask: ImageArray,
        grey_mask: ImageArray,
        black_mask: ImageArray,
        green_mask: ImageArray,
        blue_detected: bool,
        grey_detected: bool,
        black_detected: bool,
        green_detected: bool,
    ) -> ImageArray:
        """Create a clean, precise overlay following the visible wire surface on the original image."""
        overlay = image.copy()
        tint_layer = image.copy()

        if blue_detected:
            tint_layer[blue_mask == 255] = (255, 140, 0)      # Cyan / Blue
        if grey_detected:
            tint_layer[grey_mask == 255] = (215, 215, 215)    # Light Grey
        if black_detected:
            tint_layer[black_mask == 255] = (0, 165, 255)     # Radiant Amber / Orange
        if green_detected:
            tint_layer[green_mask == 255] = (50, 255, 50)     # Bright Green

        any_wire_mask = np.zeros(image.shape[:2], dtype=bool)
        if blue_detected:
            any_wire_mask |= (blue_mask == 255)
        if grey_detected:
            any_wire_mask |= (grey_mask == 255)
        if black_detected:
            any_wire_mask |= (black_mask == 255)
        if green_detected:
            any_wire_mask |= (green_mask == 255)

        blended = cv2.addWeighted(image, 0.35, tint_layer, 0.65, 0)
        overlay[any_wire_mask] = blended[any_wire_mask]

        if blue_detected:
            contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.drawContours(overlay, contours, -1, (255, 210, 60), 1, cv2.LINE_AA)

        if grey_detected:
            contours, _ = cv2.findContours(grey_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # Light grey with dark border
            cv2.drawContours(overlay, contours, -1, (40, 40, 40), 2, cv2.LINE_AA)
            cv2.drawContours(overlay, contours, -1, (245, 245, 245), 1, cv2.LINE_AA)

        if black_detected:
            contours, _ = cv2.findContours(black_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.drawContours(overlay, contours, -1, (0, 215, 255), 1, cv2.LINE_AA)

        if green_detected:
            contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(overlay, contours, -1, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.drawContours(overlay, contours, -1, (100, 255, 100), 1, cv2.LINE_AA)

        return overlay

    def _create_single_color_overlay(
        self,
        image: ImageArray,
        mask: ImageArray,
        tint_bgr: tuple[int, int, int],
        outline_bgr: tuple[int, int, int],
        is_grey: bool = False,
    ) -> ImageArray:
        """Create an annotated overlay on top of the original image with ONLY this color highlighted.

        Other regions are subtly dimmed (0.88 intensity) so the target wire sections POP.
        Never returns a raw binary mask.
        """
        dimmed = cv2.convertScaleAbs(image, alpha=0.88, beta=0)
        overlay = cv2.addWeighted(image, 0.70, dimmed, 0.30, 0)

        if np.sum(mask == 255) > 0:
            tint_layer = image.copy()
            tint_layer[mask == 255] = tint_bgr
            blended = cv2.addWeighted(image, 0.30, tint_layer, 0.70, 0)
            overlay[mask == 255] = blended[mask == 255]

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if is_grey:
                cv2.drawContours(overlay, contours, -1, (40, 40, 40), 2, cv2.LINE_AA)
                cv2.drawContours(overlay, contours, -1, (245, 245, 245), 1, cv2.LINE_AA)
            else:
                cv2.drawContours(overlay, contours, -1, (255, 255, 255), 2, cv2.LINE_AA)
                cv2.drawContours(overlay, contours, -1, outline_bgr, 1, cv2.LINE_AA)

        return overlay

    def _empty_response(
        self,
        image: ImageArray,
        source_filename: str,
        total_harness_pixels: int,
        analyzed_wire_pixels: int,
        width: int,
        height: int,
    ) -> WireColorIdentificationResponse:
        empty_colors = [
            WireColorDetail(
                color_id=cid,
                name=cname,
                status="Not detected",
                detected=False,
                pixel_count=0,
                percentage=0.0,
                confidence=0.0,
                mean_hsv=None,
                mean_lab=None,
                regions_count=0,
                overlay_color_hex=chex,
                description=f"{cname} wire not identified.",
            )
            for cid, cname, chex in (
                ("dark_blue", "Dark Blue", "#00BFFF"),
                ("grey", "Grey", "#CBD5E0"),
                ("black", "Black", "#FFA500"),
                ("green", "Green", "#00E676"),
            )
        ]
        empty_masks = {
            cid: _png_data_url(image)
            for cid in ("dark_blue", "grey", "black", "green")
        }
        return WireColorIdentificationResponse(
            source_image=source_filename,
            image_width=width,
            image_height=height,
            analyzed_wire_pixels=analyzed_wire_pixels,
            total_harness_pixels=total_harness_pixels,
            colors=empty_colors,
            sections=[],
            overlay_image=_png_data_url(image),
            original_image=_png_data_url(image),
            color_masks=empty_masks,
            production_ready=False,
            method="Colour-space thresholding with distance-transform wire isolation",
            disclaimer="No wire candidate regions found in the workpiece.",
        )
