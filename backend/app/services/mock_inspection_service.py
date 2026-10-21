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

    def evaluate(
        self,
        model: ProductModel,
        checkpoints: list[Checkpoint],
        *,
        cycle_time_seconds: float = 2.0,
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
                    bounding_box=InspectionBoundingBox(
                        x=max(0, checkpoint.reference_x - checkpoint.roi_width // 2),
                        y=max(0, checkpoint.reference_y - checkpoint.roi_height // 2),
                        width=checkpoint.roi_width,
                        height=checkpoint.roi_height,
                    ),
                )
            )

        failed = sum(result.status == "NG" for result in results)
        passed = len(results) - failed
        now = datetime.now(UTC)
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
        )
