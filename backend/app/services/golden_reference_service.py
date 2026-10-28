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

    def update_calibration(self, calibration_data: dict[str, Any]) -> dict[str, Any]:
        """Update pixel-to-mm calibration settings."""
        config = self.get_configuration()
        config["calibration"] = calibration_data
        self.save_configuration(config)
        return calibration_data

    def reset_to_baseline(self) -> dict[str, Any]:
        """Reset golden reference configuration to the baseline template."""
        default_cfg = self._default_configuration()
        self.save_configuration(default_cfg)
        return default_cfg

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
        return {
            "model_id": "GOLDEN-HARNESS-REF-001",
            "model_name": "Physical Golden Wire Harness Reference",
            "golden_image": "golden_harness.png",
            "measurement_sheet": "measurement_sheet.png",
            "image_width": 357,
            "image_height": 767,
            "specification_summary": {
                "total_terminals": 41,
                "total_junctions": 31,
                "total_nodes": 12,
                "unit": "mm",
                "source_unit": "cm",
                "unconfirmed_count": 4,
                "confirmed_count": 50,
            },
            "calibration": {
                "calibrated": True,
                "method": "top_yellow_tape_measurement",
                "known_distance_mm": 500.0,
                "pixel_distance": 458.0,
                "pixels_per_mm": 0.9160,
                "endpoint1": {"x": 0, "y": 15},
                "endpoint2": {"x": 458, "y": 15},
                "unit": "mm"
            },
            "checkpoints": []
        }


golden_reference_service = GoldenReferenceService()
