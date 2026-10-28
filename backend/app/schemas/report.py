from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.inspection import MockCheckpointResult
from app.schemas.sticker import StickerFieldData, StickerInspectionReport


class ReportBranchMeasurement(BaseModel):
    branch_id: str
    source_node_id: str
    target_node_id: str
    path_length_pixels: float = Field(ge=0)
    straight_distance_pixels: float = Field(ge=0)
    orientation_degrees: float = Field(ge=0, lt=360)
    path_length_cm: float | None = None
    straight_distance_cm: float | None = None
    unit: str = "cm"


class InspectionReportResponse(BaseModel):
    report_id: str
    inspection_id: str
    generated_at: datetime
    model_id: str
    model_name: str
    revision: str
    work_order: str
    barcode: str
    operator: str
    source_image: str
    overall_result: Literal["PASS", "NG"]
    total_checkpoints: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    warnings: int = Field(ge=0)
    cycle_time_seconds: float = Field(ge=0)
    total_wire_length_pixels: float = Field(ge=0)
    total_wire_length_cm: float | None = None
    unit: str = "cm"
    pixels_per_cm: float = 9.16
    extracted_branch_count: int = Field(ge=0)
    clustered_junction_count: int = Field(ge=0)
    terminal_count: int = Field(ge=0)
    unresolved_segment_count: int = Field(ge=0)
    annotated_image: str
    checkpoint_results: list[MockCheckpointResult]
    branch_measurements: list[ReportBranchMeasurement]
    sticker_inspection: StickerInspectionReport
    disclaimer: str
