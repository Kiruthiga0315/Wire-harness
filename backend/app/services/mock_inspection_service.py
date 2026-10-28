from __future__ import annotations

from datetime import UTC, datetime

from app.models import Checkpoint, ProductModel
from app.schemas.inspection import (
    InspectionBoundingBox,
    MockCheckpointResult,
    MockInspectionResponse,
)


class MockInspectionService:
    """Deterministic demonstration evaluator; it does not inspect image pixels."""

    ng_scenarios = {
        "CP-004": ("76 degrees", "-14 degrees", "NG — WRONG ORIENTATION", 0.943),
        "CP-008": ("Red", None, "NG — WRONG TAPE COLOUR", 0.967),
        "CP-011": ("728 mm", "-22 mm", "NG — BRANCH LENGTH SHORT", 0.951),
    }

    demo_crop_coordinates: dict[str, tuple[int, int, int, int]] = {
        "CP-001": (108, 42, 80, 70),
        "CP-002": (149, 139, 100, 100),
        "CP-003": (457, 267, 130, 120),
        "CP-004": (357, 349, 100, 100),
        "CP-005": (524, 392, 90, 80),
        "CP-006": (334, 482, 90, 80),
        "CP-007": (466, 690, 120, 150),
        "CP-008": (365, 440, 100, 100),
        "CP-009": (120, 966, 100, 110),
        "CP-010": (356, 1115, 260, 180),
        "CP-011": (393, 1331, 220, 180),
        "CP-012": (126, 1452, 90, 100),
    }

    def evaluate(
        self,
        model: ProductModel,
        checkpoints: list[Checkpoint],
        *,
        cycle_time_seconds: float = 2.0,
        image_width: int | None = None,
        image_height: int | None = None,
        table_crop: tuple[int, int, int, int] | None = None,
    ) -> MockInspectionResponse:
        results: list[MockCheckpointResult] = []
        for index, checkpoint in enumerate(checkpoints):
            scenario = self.ng_scenarios.get(checkpoint.checkpoint_id)
            if scenario:
                actual_value, deviation, reason, confidence = scenario
                status = "NG"
            else:
                actual_value = checkpoint.expected_value
                deviation = "0" if checkpoint.tolerance is not None else None
                reason = "Expected condition verified"
                confidence = round(max(0.9, 0.992 - index * 0.004), 3)
                status = "PASS"

            if table_crop is not None:
                tx, ty, tw, th = table_crop
                bounding_box = InspectionBoundingBox(
                    x=max(0, (checkpoint.reference_x - tx) - checkpoint.roi_width // 2),
                    y=max(0, (checkpoint.reference_y - ty) - checkpoint.roi_height // 2),
                    width=checkpoint.roi_width,
                    height=checkpoint.roi_height,
                )
            elif (
                image_width is not None
                and image_width <= 1000
                and checkpoint.checkpoint_id in self.demo_crop_coordinates
            ):
                cx, cy, cw, ch = self.demo_crop_coordinates[checkpoint.checkpoint_id]
                bounding_box = InspectionBoundingBox(
                    x=max(0, cx - cw // 2),
                    y=max(0, cy - ch // 2),
                    width=cw,
                    height=ch,
                )
            else:
                bounding_box = InspectionBoundingBox(
                    x=max(0, checkpoint.reference_x - checkpoint.roi_width // 2),
                    y=max(0, checkpoint.reference_y - checkpoint.roi_height // 2),
                    width=checkpoint.roi_width,
                    height=checkpoint.roi_height,
                )

            results.append(
                MockCheckpointResult(
                    checkpoint_id=checkpoint.checkpoint_id,
                    checkpoint_name=checkpoint.checkpoint_name,
                    category=checkpoint.category,
                    inspection_type=checkpoint.inspection_type,
                    expected_value=checkpoint.expected_value,
                    actual_value=actual_value,
                    tolerance=checkpoint.tolerance,
                    deviation=deviation,
                    confidence=confidence,
                    status=status,
                    status_reason=reason,
                    bounding_box=bounding_box,
                )
            )

        failed = sum(result.status == "NG" for result in results)
        passed = len(results) - failed
        now = datetime.now(UTC)
        cropped_url = "/api/test-images/active/cropped" if table_crop is not None else None
        crop_w = table_crop[2] if table_crop is not None else None
        crop_h = table_crop[3] if table_crop is not None else None
        return MockInspectionResponse(
            inspection_id=f"DEMO-{now:%Y%m%d-%H%M%S}",
            model_id=model.model_id,
            model_name=model.model_name,
            state="NG" if failed else "PASS",
            total_checkpoints=len(results),
            passed=passed,
            failed=failed,
            cycle_time_seconds=cycle_time_seconds,
            timestamp=now,
            results=results,
            cropped_image_url=cropped_url,
            crop_width=crop_w,
            crop_height=crop_h,
            is_cropped=table_crop is not None,
        )
