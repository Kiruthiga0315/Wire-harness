from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.color_inspection import ColourVector


class WireSectionROI(BaseModel):
    section_id: str
    color_id: Literal["dark_blue", "grey", "black", "green"]
    color_name: str
    status: Literal["Detected", "Uncertain", "Not detected"]
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    pixel_count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    mean_hsv: ColourVector | None = None
    mean_lab: ColourVector | None = None
    cropped_image: str  # Base64 PNG data URL of zoomed-in view with wire highlight
    original_crop: str | None = None  # Base64 PNG data URL of raw unmodified zoom crop
    overlay_color_hex: str
    description: str


class WireColorDetail(BaseModel):
    color_id: Literal["dark_blue", "grey", "black", "green"]
    name: str
    status: Literal["Detected", "Uncertain", "Not detected"]
    detected: bool
    pixel_count: int = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    mean_hsv: ColourVector | None = None
    mean_lab: ColourVector | None = None
    regions_count: int = Field(ge=0)
    overlay_color_hex: str
    description: str


class WireColorIdentificationResponse(BaseModel):
    source_image: str
    image_width: int = Field(ge=1, default=681)
    image_height: int = Field(ge=1, default=1584)
    analyzed_wire_pixels: int = Field(ge=0)
    total_harness_pixels: int = Field(ge=0)
    colors: list[WireColorDetail]
    sections: list[WireSectionROI] = Field(default_factory=list)
    overlay_image: str
    original_image: str
    color_masks: dict[str, str] = Field(default_factory=dict)
    production_ready: bool = False
    method: str
    disclaimer: str
