from typing import Literal

from pydantic import BaseModel, Field


class ColorInspectionRequest(BaseModel):
    model_id: str = Field(default="DEMO-HARNESS-001", min_length=1, max_length=80)
    checkpoint_id: str = Field(min_length=1, max_length=80)
    debug: bool = False


class ColourVector(BaseModel):
    channel_1: float
    channel_2: float
    channel_3: float


class ROIInformation(BaseModel):
    x: int
    y: int
    width: int
    height: int


class ColorInspectionResponse(BaseModel):
    model_id: str
    checkpoint_id: str
    checkpoint_name: str
    expected_colour: str
    detected_colour: str
    mean_hsv: ColourVector
    mean_lab: ColourVector
    confidence: float = Field(ge=0, le=1)
    status: Literal["PASS", "NG"]
    roi: ROIInformation
    debug_roi_image: str | None
    production_ready: bool = False
    disclaimer: str
