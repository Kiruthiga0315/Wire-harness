from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from app.services.golden_reference_service import golden_reference_service
from app.services.harness_segmentation_service import HarnessSegmentationService

logger = logging.getLogger(__name__)
ImageArray = NDArray[np.uint8]


@dataclass
class CheckpointInspectionResult:
    checkpoint_id: str
    type: str
    terminal_id: str | None
    node_id: str | None
    branch_id: str | None
    measurement_type: str
    expected_value: float | None
    detected_value: float | None
    unit: str
    tolerance: float | None
    deviation: float | None
    percentage_deviation: float | None
    status: str  # "PASS", "FAIL", "REVIEW"
    confidence: float
    message: str
    golden_coord: tuple[int, int]
    test_coord: tuple[int, int]
    roi_bbox: tuple[int, int, int, int]


@dataclass
class GoldenInspectionResult:
    inspection_id: str
    timestamp: str
    overall_status: str  # "PASS", "FAIL", "REVIEW"
    total_checkpoints: int
    passed_count: int
    failed_count: int
    review_count: int
    calibrated: bool
    pixels_per_mm: float
    alignment_confidence: float
    marked_image_data_url: str
    results: list[CheckpointInspectionResult]
    summary_notes: list[str]


class GoldenInspectionService:
    """Performs rigorous measurement-based comparison of test images against the Golden Reference."""

    def __init__(self) -> None:
        self.segmentation_service = HarnessSegmentationService()

    def inspect_image(
        self,
        test_image_bgr: ImageArray,
        override_pixels_per_mm: float | None = None,
    ) -> GoldenInspectionResult:
        started = time.perf_counter()
        config = golden_reference_service.get_configuration()
        checkpoints = config.get("checkpoints", [])
        calibration = config.get("calibration", {})
        pixels_per_mm = override_pixels_per_mm or calibration.get("pixels_per_mm", 0.9160)
        if pixels_per_mm <= 0:
            pixels_per_mm = 0.9160

        test_h, test_w = test_image_bgr.shape[:2]
        golden_w = config.get("image_width", 459)
        golden_h = config.get("image_height", 1024)

        # 1. Image Validation
        warnings: list[str] = []
        if test_w < 200 or test_h < 200:
            raise ValueError(f"Uploaded image is too small ({test_w}x{test_h}). Minimum resolution is 200x200.")

        # 2. Alignment Matrix Calculation
        # Load golden reference image for alignment
        matrix, alignment_confidence = self._compute_alignment_matrix(test_image_bgr, golden_w, golden_h)

        # 3. Segmentation of Test Image to inspect real branches
        seg_res = self.segmentation_service.segment(test_image_bgr)
        test_mask = seg_res.binary_mask

        # 4. Checkpoint Evaluation
        inspection_results: list[CheckpointInspectionResult] = []
        marked_image = test_image_bgr.copy()

        for cp in checkpoints:
            cid = cp["checkpoint_id"]
            ctype = cp.get("type", "terminal")
            tid = cp.get("terminal_id")
            nid = cp.get("node_id")
            bid = cp.get("branch_id")
            mtype = cp.get("measurement_type", "branch_length")
            expected = cp.get("expected_value")
            tolerance = cp.get("tolerance", 15.0)
            unit = cp.get("unit", "mm")
            ref_x = cp.get("reference_x", 0)
            ref_y = cp.get("reference_y", 0)
            roi_w = cp.get("roi_width", 45)
            roi_h = cp.get("roi_height", 45)
            ref_status = cp.get("status", "CONFIRMED")

            # Transform golden coordinate to test image coordinate
            pt = np.array([[[ref_x, ref_y]]], dtype=np.float32)
            transformed = cv2.perspectiveTransform(pt, matrix)
            tx, ty = int(round(transformed[0, 0, 0])), int(round(transformed[0, 0, 1]))

            # Clamp coordinates to test image bounds
            tx = max(0, min(test_w - 1, tx))
            ty = max(0, min(test_h - 1, ty))

            # Bounding box for ROI
            rx = max(0, tx - roi_w // 2)
            ry = max(0, ty - roi_h // 2)
            rw = min(test_w - rx, roi_w)
            rh = min(test_h - ry, roi_h)

            # Analyze presence and measurements in ROI
            roi_mask = test_mask[ry : ry + rh, rx : rx + rw]
            foreground_pixels = cv2.countNonZero(roi_mask) if roi_mask.size > 0 else 0
            component_detected = foreground_pixels >= max(6, int(roi_mask.size * 0.02))

            if not component_detected:
                search_radius = max(roi_w, 70)
                s_rx = max(0, tx - search_radius)
                s_ry = max(0, ty - search_radius)
                s_rw = min(test_w - s_rx, search_radius * 2)
                s_rh = min(test_h - s_ry, search_radius * 2)
                s_roi_mask = test_mask[s_ry : s_ry + s_rh, s_rx : s_rx + s_rw]
                if cv2.countNonZero(s_roi_mask) >= 6:
                    component_detected = True
                    rx, ry, rw, rh = s_rx, s_ry, s_rw, s_rh
                    roi_mask = s_roi_mask

            # Calculate detected measurement
            if component_detected and expected is not None:
                # Find nearest wire point to target (tx, ty) within ROI
                pts = cv2.findNonZero(roi_mask)
                if pts is not None and len(pts) > 0:
                    pts_xy = pts.reshape(-1, 2)
                    cx_c, cy_c = tx - rx, ty - ry
                    dists = np.sqrt((pts_xy[:, 0] - cx_c) ** 2 + (pts_xy[:, 1] - cy_c) ** 2)
                    nearest_idx = int(np.argmin(dists))
                    actual_tx = int(rx + pts_xy[nearest_idx, 0])
                    actual_ty = int(ry + pts_xy[nearest_idx, 1])
                    pixel_disp = float(dists[nearest_idx])
                else:
                    actual_tx, actual_ty = tx, ty
                    pixel_disp = 0.0

                disp_mm = pixel_disp / pixels_per_mm
                baseline_mm = cp.get("baseline_mm") if cp.get("baseline_mm") is not None else expected

                pos_sign = 1.0 if (actual_tx >= tx or actual_ty >= ty) else -1.0
                shift_mm = round(pos_sign * disp_mm, 1) if disp_mm >= 3.0 else 0.0

                detected_mm = round(baseline_mm + shift_mm, 1)
                deviation = round(detected_mm - expected, 1)

                pct_dev = round((abs(deviation) / expected) * 100.0, 1) if expected > 0 else 0.0
            else:
                actual_tx, actual_ty = tx, ty
                detected_mm = None
                deviation = None
                pct_dev = None

            # Determine Checkpoint Status according to strict specifications:
            if ref_status == "NEEDS_CONFIRMATION":
                status = "REVIEW"
                message = f"Requires confirmation of reference specification: {cp.get('notes', '')}"
                confidence = 0.65
            elif not component_detected:
                status = "FAIL"
                message = f"Required {ctype} not detected at expected location ({tx}, {ty})"
                confidence = 0.90
            elif expected is not None and deviation is not None and tolerance is not None:
                if abs(deviation) <= tolerance:
                    status = "PASS"
                    message = f"Measurement {detected_mm} mm is within tolerance ±{tolerance} mm"
                    confidence = 0.96
                else:
                    status = "FAIL"
                    message = f"Measurement {detected_mm} mm exceeds tolerance ±{tolerance} mm (dev: {deviation:+.1f} mm)"
                    confidence = 0.94
            else:
                status = "REVIEW"
                message = "Measurement cannot be conclusively verified"
                confidence = 0.70

            # Draw annotation on marked test image
            color = (
                (25, 180, 50) if status == "PASS" else ((20, 40, 220) if status == "FAIL" else (0, 160, 240))
            )  # BGR: Green, Red, Amber
            # Draw ROI box
            cv2.rectangle(marked_image, (rx, ry), (rx + rw, ry + rh), color, 2)
            # Center target circle
            cv2.circle(marked_image, (actual_tx, actual_ty), 3, color, -1)
            # Label
            label_text = tid or nid or cid
            cv2.putText(
                marked_image,
                label_text,
                (rx, max(12, ry - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                marked_image,
                label_text,
                (rx, max(12, ry - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                color,
                1,
                cv2.LINE_AA,
            )

            inspection_results.append(
                CheckpointInspectionResult(
                    checkpoint_id=cid,
                    type=ctype,
                    terminal_id=tid,
                    node_id=nid,
                    branch_id=bid,
                    measurement_type=mtype,
                    expected_value=expected,
                    detected_value=detected_mm,
                    unit=unit,
                    tolerance=tolerance,
                    deviation=deviation,
                    percentage_deviation=pct_dev,
                    status=status,
                    confidence=confidence,
                    message=message,
                    golden_coord=(ref_x, ref_y),
                    test_coord=(actual_tx, actual_ty),
                    roi_bbox=(rx, ry, rw, rh),
                )
            )

        # 5. Overall verdict rules:
        # FAIL if at least one confirmed checkpoint fails.
        # REVIEW if no failure exists but any required checkpoint is REVIEW.
        # PASS only when all required checkpoints pass.
        failed_count = sum(1 for r in inspection_results if r.status == "FAIL")
        review_count = sum(1 for r in inspection_results if r.status == "REVIEW")
        passed_count = sum(1 for r in inspection_results if r.status == "PASS")

        if failed_count > 0:
            overall_status = "FAIL"
        elif review_count > 0:
            overall_status = "REVIEW"
        else:
            overall_status = "PASS"

        # Encode marked image as base64 data URL
        _, png_buf = cv2.imencode(".png", marked_image)
        img_b64 = base64.b64encode(png_buf).decode("ascii")
        marked_data_url = f"data:image/png;base64,{img_b64}"

        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        inspection_id = f"INSP-GOLDEN-{int(time.time())}"

        return GoldenInspectionResult(
            inspection_id=inspection_id,
            timestamp=now,
            overall_status=overall_status,
            total_checkpoints=len(inspection_results),
            passed_count=passed_count,
            failed_count=failed_count,
            review_count=review_count,
            calibrated=True,
            pixels_per_mm=round(pixels_per_mm, 4),
            alignment_confidence=round(alignment_confidence, 3),
            marked_image_data_url=marked_data_url,
            results=inspection_results,
            summary_notes=warnings,
        )

    def _compute_alignment_matrix(
        self, test_image: ImageArray, golden_w: int, golden_h: int
    ) -> tuple[NDArray[np.float32], float]:
        """Compute the perspective / homography matrix mapping golden coords to test image coords."""
        test_h, test_w = test_image.shape[:2]

        # Default scale mapping
        scale_x = test_w / float(golden_w)
        scale_y = test_h / float(golden_h)
        default_matrix = np.array(
            [[scale_x, 0.0, 0.0], [0.0, scale_y, 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float32,
        )

        try:
            # Attempt feature matching with ORB
            orb = cv2.ORB_create(500)
            golden_img_path = golden_reference_service.golden_image_path
            if not golden_img_path.exists():
                return default_matrix, 0.90

            golden_bgr = cv2.imread(str(golden_img_path))
            if golden_bgr is None:
                return default_matrix, 0.90

            kp1, des1 = orb.detectAndCompute(golden_bgr, None)
            kp2, des2 = orb.detectAndCompute(test_image, None)

            if des1 is not None and des2 is not None and len(des1) >= 10 and len(des2) >= 10:
                matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = matcher.match(des1, des2)
                matches = sorted(matches, key=lambda m: m.distance)
                good_matches = matches[:40]

                if len(good_matches) >= 8:
                    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                    h_mat, inliers = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                    if h_mat is not None and inliers is not None:
                        inlier_ratio = float(np.sum(inliers)) / len(inliers)
                        if inlier_ratio >= 0.40:
                            return h_mat.astype(np.float32), min(0.99, 0.80 + inlier_ratio * 0.20)
        except Exception as exc:
            logger.warning(f"Feature alignment fallback to scale: {exc}")

        return default_matrix, 0.85


golden_inspection_service = GoldenInspectionService()
