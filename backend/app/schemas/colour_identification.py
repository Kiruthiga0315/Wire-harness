"""Pydantic schemas for the Colour Identification and Verification API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ColourVector(BaseModel):
    channel_1: float
    channel_2: float
    channel_3: float


class TapeDetectionItem(BaseModel):
    region_id: str
    detected_color: str
    bbox: list[int] = Field(min_length=4, max_length=4)
    center: list[int] = Field(min_length=2, max_length=2)
    area: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    status: str
    branch_id: str = "unassigned"
    mean_hsv: ColourVector | None = None
    mean_lab: ColourVector | None = None


class WireDetectionItem(BaseModel):
    region_id: str
    detected_color: str
    bbox: list[int] = Field(min_length=4, max_length=4)
    center: list[int] = Field(min_length=2, max_length=2)
    area: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    branch_id: str = "unassigned"
    confidence: float = Field(ge=0, le=1)
    status: str
    mean_hsv: ColourVector | None = None
    mean_lab: ColourVector | None = None


class ColourSummaryResponse(BaseModel):
    green_tape: int = Field(ge=0, default=0)
    dark_blue_tape: int = Field(ge=0, default=0)
    gray_tape: int = Field(ge=0, default=0)
    wire_regions: int = Field(ge=0, default=0)
    uncertain_detections: int = Field(ge=0, default=0)


class VerificationResponse(BaseModel):
    status: Literal["PASS", "NG", "UNCERTAIN", "NOT_CONFIGURED"]
    message: str
    details: list[dict] = Field(default_factory=list)


class ColourIdentificationRequest(BaseModel):
    inspection_id: str = Field(default="", max_length=120)
    debug: bool = False
    golden_colour_config: dict | None = None


class ColourIdentificationResponse(BaseModel):
    success: bool
    inspection_id: str
    image_width: int = Field(ge=1)
    image_height: int = Field(ge=1)
    colour_summary: ColourSummaryResponse
    tape_detections: list[TapeDetectionItem]
    wire_detections: list[WireDetectionItem]
    verification: VerificationResponse
    overlay_image: str  # base64 data URL
    original_image: str  # base64 data URL
    processing_time_ms: float = Field(ge=0)
    method: str
    disclaimer: str
    production_ready: bool = False
