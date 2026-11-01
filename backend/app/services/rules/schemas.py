from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

RuleSeverity = Literal["CRITICAL", "MAJOR", "MINOR"]
RuleStatus = Literal["PASS", "FAIL", "REVIEW", "NOT_EVALUATED", "WAIVED"]
HarnessVerdictType = Literal["ACCEPT", "REJECT", "HOLD"]
CheckSheetItemState = Literal["OK", "NG", "CORRECTED"]
BranchType = Literal["W", "X", "T", "Y", "V"]


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    value: Any
    source: str  # "vision_graph", "vision_color", "vision_ocr", "vision_quality", "operator", "dsi"
    timestamp: str | None = None
    confidence: float | None = None
    bounding_box: tuple[int, int, int, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RuleSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: str
    family: str
    name: str
    description: str = ""
    source_doc: str
    severity: RuleSeverity = "MAJOR"
    mandatory: bool = True
    zero_tolerance: bool = False
    requires_operator_attestation: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    rule_id: str
    family: str
    name: str
    source_doc: str
    severity: RuleSeverity
    status: RuleStatus
    mandatory: bool = True
    expected: Any = None
    actual: Any = None
    tolerance: Any = None
    deviation: Any = None
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    reason: str = ""
    reaction_plan: str = ""


class OperatorAttestation(BaseModel):
    user_id: str
    user_name: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
    attested: bool = True
    notes: str = ""


class CheckSheetEntry(BaseModel):
    first_piece: CheckSheetItemState = "OK"
    last_piece: CheckSheetItemState = "OK"
    notes: str | None = None


class FinalAssemblyCheckSheetInput(BaseModel):
    shift: str = "A"
    date: str = Field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d"))
    part_no: str = "YH200502"
    associate_name: str = ""
    e_code: str = ""
    total_production_qty: int = 1
    label_serial_from: int = 100001
    label_serial_to: int = 100001
    label_serial_scrapped: int = 0
    checks: dict[str, CheckSheetEntry] = Field(default_factory=dict)


class BranchTapingInput(BaseModel):
    branch_id: str
    branch_type: BranchType = "W"
    laps: int | None = None
    cycle_time_seconds: float | None = None
    cross_taping_present: bool = False
    excess_taping: bool = False
    loose_taping: bool = False
    step_laps: int | None = None
    completion_laps: int | None = None
    extension_mm: float | None = 30.0


class OperatorInput(BaseModel):
    check_sheet: FinalAssemblyCheckSheetInput | None = None
    branch_taping: list[BranchTapingInput] = Field(default_factory=list)
    master_sample_status: Literal["OK", "NG", "EXPIRED"] | None = "OK"
    attestations: dict[str, OperatorAttestation] = Field(default_factory=dict)
    dsi_test_result: dict[str, Any] | None = None  # Pluggable DSI adapter integration


class ImageQualityMetrics(BaseModel):
    sharpness_laplacian: float = 0.0
    mean_brightness: float = 0.0
    dark_clipping_ratio: float = 0.0
    bright_clipping_ratio: float = 0.0
    passed: bool = True
    failure_reasons: list[str] = Field(default_factory=list)


class VisionEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    calibrated: bool = False
    pixels_per_mm: float = 0.0
    calibration_provenance: str = "uncalibrated"
    alignment_confidence: float = 1.0
    image_quality: ImageQualityMetrics = Field(default_factory=ImageQualityMetrics)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    graph_branches: list[dict[str, Any]] = Field(default_factory=list)
    graph_nodes: list[dict[str, Any]] = Field(default_factory=list)
    colored_tapes: dict[str, Any] = Field(default_factory=dict)
    sticker_data: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)


class InspectionContext(BaseModel):
    vision: VisionEvidence
    operator: OperatorInput = Field(default_factory=OperatorInput)
    variant: str = "YH200502"
    part_no: str = "YH200502"
    image_hash: str = ""


class HarnessVerdict(BaseModel):
    verdict_id: str
    timestamp: str
    verdict: HarnessVerdictType
    variant: str
    part_no: str
    rule_pack_version: str = "1.0.0"
    calibration_provenance: str = "uncalibrated"
    image_hash: str = ""
    rule_results: list[RuleResult] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)
    reaction_plan: str = ""
    reasons: list[str] = Field(default_factory=list)
