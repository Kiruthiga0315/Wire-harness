from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MockInspectionRequest(BaseModel):
    model_id: str = Field(default="DEMO-HARNESS-001", min_length=1, max_length=80)


class InspectionBoundingBox(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class MockCheckpointResult(BaseModel):
    checkpoint_id: str
    checkpoint_name: str
    category: str
    inspection_type: str
    expected_value: str | None
    actual_value: str | None
    tolerance: float | None
    deviation: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["PASS", "NG"]
    status_reason: str
    bounding_box: InspectionBoundingBox


class MockInspectionResponse(BaseModel):
    inspection_id: str
    model_id: str
    model_name: str
    state: Literal["PASS", "NG"]
    total_checkpoints: int
    passed: int
    failed: int
    warnings: int = 0
    cycle_time_seconds: float
    timestamp: datetime
    results: list[MockCheckpointResult]
    cropped_image_url: str | None = None
    crop_width: int | None = None
    crop_height: int | None = None
    is_cropped: bool = False
