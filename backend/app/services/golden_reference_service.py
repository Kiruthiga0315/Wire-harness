from __future__ import annotations

import csv
import io
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class CheckpointItem:
    checkpoint_id: str
    type: str  # "terminal", "junction", "node_distance", "branch"
    terminal_id: str | None
    node_id: str | None
    branch_id: str | None
    measurement_type: str  # "branch_length", "node_to_node_distance", "presence"
    expected_value: float | None
    unit: str  # "mm"
    tolerance: float | None
    reference_x: int
    reference_y: int
    roi_width: int = 45
    roi_height: int = 45
    confidence: float = 0.95
    status: str = "CONFIRMED"  # "CONFIRMED", "NEEDS_CONFIRMATION", "REVIEW"
    notes: str = ""


class GoldenReferenceService:
    """Manages the persistent physical golden wire harness reference and measurement specifications."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or (get_settings().project_root / "data" / "golden_reference")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.data_dir / "golden_measurements.json"
        self.csv_path = self.data_dir / "golden_measurements.csv"
        self.golden_image_path = self.data_dir / "golden_harness.png"
        if not self.golden_image_path.exists():
            alt_jpg = self.data_dir / "golden_harness.jpg"
            if alt_jpg.exists():
                self.golden_image_path = alt_jpg
        self.sheet_image_path = self.data_dir / "measurement_sheet.png"

    def get_configuration(self) -> dict[str, Any]:
        """Load and return the complete golden reference configuration."""
        if not self.json_path.exists():
            return self._default_configuration()
        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Recompute specification summary counts dynamically
            cps = data.get("checkpoints", [])
            for c in cps:
                if "baseline_mm" not in c and c.get("expected_value") is not None:
                    c["baseline_mm"] = c["expected_value"]
            data["specification_summary"] = {
                "total_checkpoints": len(cps),
                "total_terminals": sum(1 for c in cps if c.get("type") == "terminal"),
                "total_nodes": sum(1 for c in cps if c.get("type") == "node_distance"),
                "confirmed_count": sum(1 for c in cps if c.get("status") == "CONFIRMED"),
                "unconfirmed_count": sum(1 for c in cps if c.get("status") == "NEEDS_CONFIRMATION"),
                "unit": "mm",
                "source_unit": "cm",
            }
            return data
        except Exception as exc:
            logger.error(f"Error loading golden config: {exc}")
            return self._default_configuration()

    def save_configuration(self, config: dict[str, Any]) -> dict[str, Any]:
        """Save configuration to both JSON and CSV files."""
        # Recalculate summary
        cps = config.get("checkpoints", [])
        config["specification_summary"] = {
            "total_checkpoints": len(cps),
            "total_terminals": sum(1 for c in cps if c.get("type") == "terminal"),
            "total_nodes": sum(1 for c in cps if c.get("type") == "node_distance"),
            "confirmed_count": sum(1 for c in cps if c.get("status") == "CONFIRMED"),
            "unconfirmed_count": sum(1 for c in cps if c.get("status") == "NEEDS_CONFIRMATION"),
            "unit": "mm",
            "source_unit": "cm",
        }
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        self._export_csv_file(config.get("checkpoints", []))
        return config

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Find a single checkpoint by id."""
        config = self.get_configuration()
        for cp in config.get("checkpoints", []):
            if cp.get("checkpoint_id") == checkpoint_id:
                return cp
        return None

    def update_checkpoint(self, checkpoint_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update a single checkpoint's properties (measurement, status, coordinates)."""
        config = self.get_configuration()
        checkpoints = config.get("checkpoints", [])
        updated = False
        target_cp = None

        for cp in checkpoints:
            if cp.get("checkpoint_id") == checkpoint_id:
                for key, val in updates.items():
                    if key in cp:
                        cp[key] = val
                target_cp = cp
                updated = True
                break

        if not updated:
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        self.save_configuration(config)
        return target_cp

    def add_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        """Add a new checkpoint to the golden reference."""
        config = self.get_configuration()
        checkpoints = config.setdefault("checkpoints", [])
        cid = checkpoint.get("checkpoint_id")
        if not cid:
            raise ValueError("checkpoint_id is required")

        # Check for duplicate
        for cp in checkpoints:
            if cp.get("checkpoint_id") == cid:
                raise ValueError(f"Checkpoint with id '{cid}' already exists")

        checkpoints.append(checkpoint)
        self.save_configuration(config)
        return checkpoint

    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Remove a checkpoint from the golden reference."""
        config = self.get_configuration()
        checkpoints = config.get("checkpoints", [])
        filtered = [cp for cp in checkpoints if cp.get("checkpoint_id") != checkpoint_id]
        if len(filtered) == len(checkpoints):
            raise KeyError(f"Checkpoint not found: {checkpoint_id}")

        config["checkpoints"] = filtered
        self.save_configuration(config)

    def clear_all_checkpoints(self) -> dict[str, Any]:
        """Remove all checkpoints from the golden reference configuration."""
        config = self.get_configuration()
        config["checkpoints"] = []
        self.save_configuration(config)
        try:
            from app.core.database import SessionLocal
            from app.models.checkpoint import Checkpoint
            from sqlalchemy import delete
            with SessionLocal() as db:
                db.execute(delete(Checkpoint).where(Checkpoint.model_id == "DEMO-HARNESS-001"))
                db.commit()
        except Exception as exc:
            logger.warning(f"Failed to clear SQLite checkpoints: {exc}")
        return self.get_configuration()

    def update_calibration(self, calibration_data: dict[str, Any]) -> dict[str, Any]:
        """Update pixel-to-mm calibration settings."""
        config = self.get_configuration()
        config["calibration"] = calibration_data
        self.save_configuration(config)
        return calibration_data

    def sync_with_active_image(self) -> dict[str, Any]:
        """Synchronize the Golden Reference configuration, image, and checkpoints with the currently active test image."""
        import math
        import cv2
        from app.services.active_image_service import active_image_service
        from app.services.feature_extraction_service import FeatureExtractionService
        from app.services.calibration_service import detect_tape_calibration, pixels_per_cm_for_width

        active = active_image_service.get_active_image()
        if active is None or active.bgr_image is None:
            raise RuntimeError("No active test image is loaded to sync with Golden Reference.")

        img = active.bgr_image
        h, w = img.shape[:2]

        # 1. Back up baseline golden image if not already backed up
        baseline_backup = self.data_dir / "golden_harness_baseline.png"
        if not baseline_backup.exists() and self.golden_image_path.exists():
            try:
                baseline_backup.write_bytes(self.golden_image_path.read_bytes())
            except Exception as e:
                logger.warning(f"Failed to backup baseline golden image: {e}")

        # 2. Overwrite / update golden_harness.png with active image
        golden_png = self.data_dir / "golden_harness.png"
        cv2.imwrite(str(golden_png), img)
        self.golden_image_path = golden_png

        # Also backup baseline JSON if not already backed up
        baseline_json = self.data_dir / "golden_measurements_baseline.json"
        if not baseline_json.exists() and self.json_path.exists():
            try:
                baseline_json.write_bytes(self.json_path.read_bytes())
            except Exception as e:
                logger.warning(f"Failed to backup baseline golden json: {e}")

        # 3. Load baseline config to get canonical checkpoints
        base_cfg = self._default_configuration()
        if baseline_json.exists():
            try:
                with open(baseline_json, "r", encoding="utf-8") as f:
                    base_cfg = json.load(f)
            except Exception:
                pass
        elif self.json_path.exists():
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    base_cfg = json.load(f)
            except Exception:
                pass

        golden_w = float(base_cfg.get("image_width", 1800) or 1800)
        golden_h = float(base_cfg.get("image_height", 560) or 560)

        scale_x = float(w) / golden_w
        scale_y = float(h) / golden_h
        scale_roi = math.sqrt(scale_x * scale_y) if (scale_x > 0 and scale_y > 0) else 1.0

        is_same_scale = abs(scale_x - 1.0) < 0.02 and abs(scale_y - 1.0) < 0.02

        # Extract features for keypoint snapping only when scaling between different dimensions
        snapping_keypoints: list[tuple[int, int]] = []
        if not is_same_scale:
            try:
                fe = FeatureExtractionService().extract_features(img)
                snapping_keypoints = [
                    (ep.x, ep.y) for ep in fe.skeleton_features.endpoint_candidates
                ] + [
                    (j.x, j.y) for j in fe.skeleton_features.junction_candidates
                ]
            except Exception as exc:
                logger.warning(f"Feature snapping extraction warning: {exc}")

        # 4. Scale and snap all checkpoints
        scaled_checkpoints: list[dict[str, Any]] = []
        for gcp in base_cfg.get("checkpoints", []):
            cp_copy = dict(gcp)
            raw_x = gcp.get("reference_x", 0)
            raw_y = gcp.get("reference_y", 0)
            if is_same_scale:
                ref_x = raw_x
                ref_y = raw_y
            else:
                ref_x = int(round(raw_x * scale_x))
                ref_y = int(round(raw_y * scale_y))

                # Snap to detected skeleton keypoint if within 65px radius
                if snapping_keypoints:
                    closest = min(snapping_keypoints, key=lambda p: math.hypot(p[0] - ref_x, p[1] - ref_y))
                    if math.hypot(closest[0] - ref_x, closest[1] - ref_y) <= 65.0:
                        ref_x, ref_y = int(closest[0]), int(closest[1])

            cp_copy["reference_x"] = ref_x
            cp_copy["reference_y"] = ref_y
            cp_copy["roi_width"] = max(35, min(80, int(round(gcp.get("roi_width", 45) * scale_roi))))
            cp_copy["roi_height"] = max(35, min(80, int(round(gcp.get("roi_height", 45) * scale_roi))))
            cp_copy["status"] = "CONFIRMED"
            scaled_checkpoints.append(cp_copy)

        # 5. Calibration for the new workpiece
        calib_result = detect_tape_calibration(img)
        if calib_result.get("pixels_per_cm") and float(calib_result["pixels_per_cm"]) > 0.5:
            px_per_cm = float(calib_result["pixels_per_cm"])
            px_per_mm = round(px_per_cm / 10.0, 4)
        else:
            px_per_cm = pixels_per_cm_for_width(w)
            px_per_mm = round(px_per_cm / 10.0, 4)

        new_config: dict[str, Any] = {
            "model_id": "GOLDEN-HARNESS-REF-001",
            "model_name": f"Synchronized Reference: {active.filename}",
            "golden_image": "golden_harness.png",
            "measurement_sheet": "measurement_sheet.png",
            "image_width": w,
            "image_height": h,
            "calibration": {
                "calibrated": True,
                "method": calib_result.get("method", "tape_or_proportional"),
                "known_distance_mm": float(calib_result.get("tape_cm_span", 50.0) or 50.0) * 10.0,
                "pixel_distance": float(calib_result.get("tape_pixel_span", 500.0) or 500.0),
                "pixels_per_mm": px_per_mm,
                "unit": "mm",
            },
            "checkpoints": scaled_checkpoints,
        }

        self.save_configuration(new_config)

        # 6. Also sync the SQLite Checkpoints table for consistency
        try:
            from app.core.database import SessionLocal
            from app.services.checkpoint_service import CheckpointService
            with SessionLocal() as db:
                CheckpointService(db).sync_from_golden_reference(
                    model_id="DEMO-HARNESS-001",
                    replace=True,
                    scale_to_active_image=True,
                )
        except Exception as exc:
            logger.warning(f"Failed to sync SQLite checkpoints during golden sync: {exc}")

        return self.get_configuration()

    def reset_to_baseline(self) -> dict[str, Any]:
        """Reset golden reference configuration to the baseline template."""
        baseline_backup = self.data_dir / "golden_harness_baseline.png"
        golden_png = self.data_dir / "golden_harness.png"
        if baseline_backup.exists():
            golden_png.write_bytes(baseline_backup.read_bytes())
            self.golden_image_path = golden_png

        baseline_json = self.data_dir / "golden_measurements_baseline.json"
        data = None
        if baseline_json.exists():
            try:
                with open(baseline_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.save_configuration(data)
            except Exception:
                pass

        if data is None:
            data = self._default_configuration()
            self.save_configuration(data)

        try:
            from app.core.database import SessionLocal
            from app.services.checkpoint_service import CheckpointService
            with SessionLocal() as db:
                CheckpointService(db).sync_from_golden_reference(
                    model_id="DEMO-HARNESS-001",
                    replace=True,
                    scale_to_active_image=True,
                )
        except Exception as exc:
            logger.warning(f"Failed to sync SQLite checkpoints during reset: {exc}")

        return data

    def export_csv(self) -> str:
        """Export current checkpoints as a CSV string."""
        config = self.get_configuration()
        checkpoints = config.get("checkpoints", [])
        fieldnames = [
            "checkpoint_id", "type", "terminal_id", "node_id", "branch_id",
            "measurement_type", "expected_value", "unit", "tolerance",
            "reference_x", "reference_y", "roi_width", "roi_height",
            "confidence", "status", "notes"
        ]
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for cp in checkpoints:
            row = {k: cp.get(k, "") for k in fieldnames}
            writer.writerow(row)
        return output.getvalue()

    def _export_csv_file(self, checkpoints: list[dict[str, Any]]) -> None:
        fieldnames = [
            "checkpoint_id", "type", "terminal_id", "node_id", "branch_id",
            "measurement_type", "expected_value", "unit", "tolerance",
            "reference_x", "reference_y", "roi_width", "roi_height",
            "confidence", "status", "notes"
        ]
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for cp in checkpoints:
                row = {k: cp.get(k, "") for k in fieldnames}
                writer.writerow(row)

    def _default_configuration(self) -> dict[str, Any]:
        baseline_file = self.data_dir / "golden_measurements_baseline.json"
        if baseline_file.exists():
            try:
                with open(baseline_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read baseline file: {e}")
        return {
            "model_id": "GOLDEN-HARNESS-REF-001",
            "model_name": "Synchronized Reference: 001_01_board_crop.png",
            "golden_image": "golden_harness.png",
            "measurement_sheet": "measurement_sheet.png",
            "image_width": 1800,
            "image_height": 560,
            "specification_summary": {
                "total_checkpoints": 34,
                "total_terminals": 34,
                "total_junctions": 0,
                "total_nodes": 0,
                "unit": "mm",
                "source_unit": "cm",
                "unconfirmed_count": 0,
                "confirmed_count": 34,
            },
            "calibration": {
                "calibrated": True,
                "method": "manual_calibration",
                "known_distance_mm": 500.0,
                "pixel_distance": 980.4,
                "pixels_per_mm": 1.9608,
                "endpoint1": {"x": 0, "y": 15},
                "endpoint2": {"x": 980, "y": 15},
                "unit": "mm"
            },
            "checkpoints": []
        }


golden_reference_service = GoldenReferenceService()
