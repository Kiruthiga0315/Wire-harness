from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import yaml

from app.core.settings import get_settings

logger = logging.getLogger(__name__)


class RulePackValidationError(ValueError):
    """Raised when a rule pack YAML fails schema or integrity validation."""


class RulePackLoader:
    """Loads, validates, and caches versioned YAML rule packs."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        self.rules_dir = rules_dir or (get_settings().project_root / "data" / "rules")
        self._cache: dict[str, dict[str, Any]] = {}

    def get_pack(self, pack_id: str) -> dict[str, Any]:
        if pack_id in self._cache:
            return self._cache[pack_id]

        file_path = self.rules_dir / f"{pack_id}.yaml"
        if not file_path.exists():
            raise FileNotFoundError(f"Rule pack YAML file not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:
            raise RulePackValidationError(f"Malformed YAML in {file_path.name}: {exc}") from exc

        self._validate_pack(pack_id, data)
        self._cache[pack_id] = data
        return data

    def load_all_packs(self) -> dict[str, dict[str, Any]]:
        expected_packs = [
            "msil_tolerances",
            "taping_standard",
            "visual_inspection_wi79",
            "final_assembly_frm19",
            "ptdb_yh200502",
        ]
        packs = {}
        for pid in expected_packs:
            packs[pid] = self.get_pack(pid)
        return packs

    def _validate_pack(self, pack_id: str, data: dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise RulePackValidationError(f"Rule pack '{pack_id}' must be a YAML dictionary")

        if "version" not in data:
            raise RulePackValidationError(f"Rule pack '{pack_id}' is missing required 'version' field")

        if pack_id == "msil_tolerances":
            if "nominal_classes" not in data or not isinstance(data["nominal_classes"], list):
                raise RulePackValidationError("msil_tolerances requires 'nominal_classes' list")
            if "subject_column_mapping" not in data:
                raise RulePackValidationError("msil_tolerances requires 'subject_column_mapping'")

        elif pack_id == "taping_standard":
            if "branch_types" not in data or not isinstance(data["branch_types"], dict):
                raise RulePackValidationError("taping_standard requires 'branch_types' mapping")
            for btype in ("W", "X", "T", "Y", "V"):
                if btype not in data["branch_types"]:
                    raise RulePackValidationError(f"taping_standard missing branch type '{btype}'")

        elif pack_id == "visual_inspection_wi79":
            if "rules" not in data or not isinstance(data["rules"], list):
                raise RulePackValidationError("visual_inspection_wi79 requires 'rules' list")

        elif pack_id == "final_assembly_frm19":
            if "check_items" not in data or not isinstance(data["check_items"], list):
                raise RulePackValidationError("final_assembly_frm19 requires 'check_items' list")

        elif pack_id == "ptdb_yh200502":
            if "concerns" not in data or not isinstance(data["concerns"], list):
                raise RulePackValidationError("ptdb_yh200502 requires 'concerns' list")
            if len(data["concerns"]) != 23:
                logger.warning(
                    "ptdb_yh200502 has %d concerns (expected 23 MSIL concerns)",
                    len(data["concerns"]),
                )


rule_pack_loader = RulePackLoader()
