from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class StickerFieldData(BaseModel):
    harness_code: str | None = None
    part_number: str | None = None
    description: str | None = None
    drawing_number: str | None = None
    serial_number: str | None = None
    barcode_payload: str | None = None
    supplier: str | None = None
    batch_code: str | None = None


class StickerInspectionReport(BaseModel):
    present: bool
    status: Literal["PRESENT", "NOT_PRESENT"]
    notification: str
    confidence: float = Field(ge=0.0, le=1.0)
    fields: StickerFieldData
    thumbnail: str | None = None
