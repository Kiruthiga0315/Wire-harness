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
    path_length_pixels: float = Field(ge=0)
    straight_distance_pixels: float = Field(ge=0)
    orientation_degrees: float = Field(ge=0, lt=360)
    path_length_cm: float | None = None
    straight_distance_cm: float | None = None
    unit: str = "cm"


class JunctionTerminalDistanceResponse(BaseModel):
    junction_node_id: str
    terminal_node_id: str
    path_distance_pixels: float = Field(ge=0)
    straight_distance_pixels: float = Field(ge=0)
    path_distance_cm: float | None = None
    straight_distance_cm: float | None = None
    unit: str = "cm"


class BranchPairDistanceResponse(BaseModel):
    junction_node_id: str
    first_branch_id: str
    second_branch_id: str
    via_junction_distance_pixels: float = Field(ge=0)
    midpoint_straight_distance_pixels: float = Field(ge=0)
    angular_separation_degrees: float = Field(ge=0, le=180)
    via_junction_distance_cm: float | None = None
    midpoint_straight_distance_cm: float | None = None
    unit: str = "cm"


class HarnessGraphMeasurements(BaseModel):
    length_method: str
    orientation_convention: str
    branch_distance_definition: str
    nodes: list[GraphNodeResponse]
    node_to_node_distances: list[GraphBranchResponse]
    nearest_junction_to_terminal_distances: list[JunctionTerminalDistanceResponse]
    branch_to_branch_distances: list[BranchPairDistanceResponse]


class HarnessGraphResponse(BaseModel):
    source_image: str
    production_ready: bool
    disclaimer: str
    metrics: HarnessGraphMetrics
    endpoints: list[GraphPointResponse]
    junctions: list[GraphPointResponse]
    measurements: HarnessGraphMeasurements
    images: HarnessGraphImages
