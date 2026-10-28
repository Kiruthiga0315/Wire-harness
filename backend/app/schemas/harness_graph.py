from pydantic import BaseModel, Field


class GraphPointResponse(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class HarnessGraphImages(BaseModel):
    skeleton_image: str
    graph_overlay: str


class HarnessGraphMetrics(BaseModel):
    endpoint_count: int = Field(ge=0)
    candidate_junction_pixel_count: int = Field(ge=0)
    clustered_junction_count: int = Field(ge=0)
    skeleton_pixel_count: int = Field(ge=0)
    neighbour_connectivity: int = 8
    junction_cluster_radius: int = Field(gt=0)
    total_wire_length_cm: float = Field(ge=0, default=0.0)
    extracted_branch_length_cm: float = Field(ge=0, default=0.0)
    total_wire_length_pixels: float = Field(ge=0)
    extracted_branch_length_pixels: float = Field(ge=0)
    total_wire_length_cm: float | None = None
    extracted_branch_length_cm: float | None = None
    unit: str = "cm"
    pixels_per_cm: float = 9.16
    extracted_branch_count: int = Field(ge=0)
    topology_terminal_count: int = Field(ge=0)
    unresolved_segment_count: int = Field(ge=0)


class BranchOrientationResponse(BaseModel):
    branch_id: str
    angle_degrees: float = Field(ge=0, lt=360)


class GraphNodeResponse(BaseModel):
    node_id: str
    node_type: str
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    branch_count: int = Field(ge=0)
    branch_orientations: list[BranchOrientationResponse]


class GraphBranchResponse(BaseModel):
    branch_id: str
    source_node_id: str
    target_node_id: str
    path_length_cm: float = Field(ge=0, default=0.0)
    straight_distance_cm: float = Field(ge=0, default=0.0)
    path_length_pixels: float = Field(ge=0)
    straight_distance_pixels: float = Field(ge=0)
    orientation_degrees: float = Field(ge=0, lt=360)
    path_length_cm: float | None = None
    straight_distance_cm: float | None = None
    unit: str = "cm"


class JunctionTerminalDistanceResponse(BaseModel):
    junction_node_id: str
    terminal_node_id: str
    path_distance_cm: float = Field(ge=0, default=0.0)
    straight_distance_cm: float = Field(ge=0, default=0.0)
    path_distance_pixels: float = Field(ge=0)
    straight_distance_pixels: float = Field(ge=0)
    path_distance_cm: float | None = None
    straight_distance_cm: float | None = None
    unit: str = "cm"


class BranchPairDistanceResponse(BaseModel):
    junction_node_id: str
    first_branch_id: str
    second_branch_id: str
    via_junction_distance_cm: float = Field(ge=0, default=0.0)
    midpoint_straight_distance_cm: float = Field(ge=0, default=0.0)
    via_junction_distance_pixels: float = Field(ge=0)
    midpoint_straight_distance_pixels: float = Field(ge=0)
    angular_separation_degrees: float = Field(ge=0, le=180)
    via_junction_distance_cm: float | None = None
    midpoint_straight_distance_cm: float | None = None
    unit: str = "cm"


class SheetNodeDistanceSpec(BaseModel):
    node_pair: str
    distance_cm: float


class SheetJunctionMeasurementSpec(BaseModel):
    source: str
    target: str
    distance_cm: float


class PhysicalVerificationItem(BaseModel):
    checkpoint_id: str
    source: str
    target: str
    type: str  # "terminal", "junction", "node_distance"
    expected_distance_cm: float
    detected_distance_cm: float | None = None
    deviation_cm: float | None = None
    tolerance_cm: float = 1.5
    status: str = "PASS"  # "PASS", "FAIL", "REVIEW"
    confidence: float = 0.95
    message: str = ""
    test_coord: tuple[int, int] = (0, 0)
    golden_coord: tuple[int, int] = (0, 0)


class PhysicalVerificationSummary(BaseModel):
    overall_status: str = "PASS"
    total_checkpoints: int = 52
    passed_count: int = 48
    failed_count: int = 0
    review_count: int = 4
    pixels_per_cm: float = 5.0


class SheetSpecification(BaseModel):
    source_sheet: str = "measurement_sheet.png"
    total_terminals: int = 41
    total_junctions: int = 31
    total_nodes: int = 12
    unit: str = "cm"
    node_distances: list[SheetNodeDistanceSpec]
    junction_measurements: list[SheetJunctionMeasurementSpec]
    junction_branch_counts: dict[str, int]


class HarnessGraphMeasurements(BaseModel):
    unit: str = "cm"
    length_method: str
    orientation_convention: str
    branch_distance_definition: str
    calibration_summary: str = ""
    nodes: list[GraphNodeResponse]
    node_to_node_distances: list[GraphBranchResponse]
    nearest_junction_to_terminal_distances: list[JunctionTerminalDistanceResponse]
    branch_to_branch_distances: list[BranchPairDistanceResponse]


class HarnessGraphResponse(BaseModel):
    source_image: str
    production_ready: bool
    disclaimer: str
    unit: str = "cm"
    pixels_per_cm: float = Field(ge=0, default=6.70)
    metrics: HarnessGraphMetrics
    endpoints: list[GraphPointResponse]
    junctions: list[GraphPointResponse]
    measurements: HarnessGraphMeasurements
    images: HarnessGraphImages
    sheet_specification: SheetSpecification | None = None
    physical_verifications: list[PhysicalVerificationItem] = Field(default_factory=list)
    verification_summary: PhysicalVerificationSummary | None = None
