from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckpointFields(BaseModel):
    checkpoint_name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=80)
    inspection_type: str = Field(min_length=1, max_length=80)
    expected_value: str | None = Field(default=None, max_length=180)
    tolerance: float | None = Field(default=None, ge=0)
    reference_x: int = Field(ge=0, le=50_000)
    reference_y: int = Field(ge=0, le=50_000)
    roi_width: int = Field(default=80, ge=1, le=10_000)
    roi_height: int = Field(default=80, ge=1, le=10_000)
    enabled: bool = True


class CheckpointCreate(CheckpointFields):
    checkpoint_id: str | None = Field(default=None, min_length=1, max_length=80)


class CheckpointUpdate(BaseModel):
    checkpoint_name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, min_length=1, max_length=80)
    inspection_type: str | None = Field(default=None, min_length=1, max_length=80)
    expected_value: str | None = Field(default=None, max_length=180)
    tolerance: float | None = Field(default=None, ge=0)
    reference_x: int | None = Field(default=None, ge=0, le=50_000)
    reference_y: int | None = Field(default=None, ge=0, le=50_000)
    roi_width: int | None = Field(default=None, ge=1, le=10_000)
    roi_height: int | None = Field(default=None, ge=1, le=10_000)
    enabled: bool | None = None


class CheckpointRead(CheckpointFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    checkpoint_id: str
    model_id: str
    created_at: datetime
    updated_at: datetime
