from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ImageDimensions(BaseModel):
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    channels: int = Field(..., description="Number of image channels")


class BoundingBox(BaseModel):
    x: int = Field(..., description="Top-left x coordinate")
    y: int = Field(..., description="Top-left y coordinate")
    width: int = Field(..., description="Bounding box width")
    height: int = Field(..., description="Bounding box height")


class EdgeStatistics(BaseModel):
    total_edge_pixels: int = Field(..., description="Total edge pixels detected in image")
    edge_density: float = Field(..., description="Ratio of edge pixels to total image pixels")
    boundary_edge_pixels: int = Field(..., description="Edge pixels belonging to wire/harness boundaries")
    filtered_background_edges: int = Field(..., description="Estimated background noise edges filtered out")


class ContourDescriptor(BaseModel):
    contour_id: int
    area: float
    perimeter: float
    bounding_box: BoundingBox
    aspect_ratio: float
    solidity: float
    extent: float
    is_internal: bool
    hierarchy_level: int


class MainHarnessContour(BaseModel):
    area: float
    perimeter: float
    bounding_box: BoundingBox
    aspect_ratio: float
    solidity: float
    extent: float
    center_x: float
    center_y: float


class ContourInformation(BaseModel):
    total_contours: int
    external_contours_count: int
    internal_contours_count: int
    main_harness_contour: MainHarnessContour | None = None
    significant_contours: list[ContourDescriptor] = Field(default_factory=list)


class EndpointCandidate(BaseModel):
    id: str
    x: int
    y: int
    tangent_angle_deg: float = Field(..., description="Tangent orientation angle at endpoint in degrees [0, 360)")
    connection_degree: int = Field(1, description="Number of connected branches (1 for genuine endpoint)")


class JunctionCandidate(BaseModel):
    id: str
    x: int
    y: int
    branch_count: int
    is_simple_crossing: bool = Field(
        ...,
        description="True if junction exhibits orthogonal/pass-through geometry typical of visual wire overlap rather than spliced electrical joint",
    )
    branch_angles_deg: list[float] = Field(default_factory=list)


class BranchFeature(BaseModel):
    branch_id: str
    start_node: str
    end_node: str
    path_length_pixels: float = Field(..., description="Uncalibrated along-skeleton path length in pixels")
    straight_distance_pixels: float = Field(..., description="Euclidean distance between endpoints in pixels")
    straightness_ratio: float = Field(..., description="straight_distance / path_length (1.0 = perfectly straight)")
    orientation_deg: float = Field(..., description="Overall branch orientation in degrees [0, 360)")
    mean_curvature: float = Field(..., description="Mean curvature along the branch path")
    max_bend_angle_deg: float = Field(..., description="Maximum local bend angle observed along the branch")
    compact_path: list[list[int]] = Field(default_factory=list, description="Subsampled or keypoint coordinates [[x, y], ...]")


class SkeletonFeatures(BaseModel):
    total_wire_length_pixels: float
    uncalibrated: bool = True
    skeleton_pixel_count: int
    endpoint_candidates: list[EndpointCandidate] = Field(default_factory=list)
    junction_candidates: list[JunctionCandidate] = Field(default_factory=list)
    branches: list[BranchFeature] = Field(default_factory=list)


class CandidateRegionForPartId(BaseModel):
    candidate_type: Literal["TERMINAL_CANDIDATE", "JOINT_CANDIDATE", "CONNECTOR_CANDIDATE"]
    associated_node_id: str
    bounding_box: BoundingBox
    local_area: float
    local_aspect_ratio: float
    note: str = Field(
        "Candidate keypoint region; coordinates and bounding region provided for Part Identification module.",
        description="Explanation that candidate requires classification confirmation by Part Identification",
    )


class PairwiseDistance(BaseModel):
    from_node: str
    to_node: str
    distance_pixels: float


class GeometricFeatures(BaseModel):
    mean_branch_straightness: float
    max_bend_angle_deg: float
    total_detected_joints: int
    total_detected_terminals: int
    pairwise_feature_distances: list[PairwiseDistance] = Field(default_factory=list)


class FeatureVisualizations(BaseModel):
    original_preprocessed: str | None = None
    edge_map: str | None = None
    contour_visualization: str | None = None
    skeleton_visualization: str | None = None
    keypoint_junction_visualization: str | None = None
    combined_overlay: str | None = None


class FeatureExtractionRequest(BaseModel):
    canny_low_threshold: int = Field(50, ge=5, le=250)
    canny_high_threshold: int = Field(150, ge=10, le=255)
    min_contour_area: float = Field(30.0, ge=1.0)
    curvature_window: int = Field(7, ge=3, le=31)
    generate_visualizations: bool = True


class FeatureExtractionResponse(BaseModel):
    image_dimensions: ImageDimensions
    edge_statistics: EdgeStatistics
    contour_information: ContourInformation
    skeleton_features: SkeletonFeatures
    candidate_regions_for_part_id: list[CandidateRegionForPartId] = Field(default_factory=list)
    geometric_features: GeometricFeatures
    visualizations: FeatureVisualizations | None = None
    processing_time_ms: float
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
