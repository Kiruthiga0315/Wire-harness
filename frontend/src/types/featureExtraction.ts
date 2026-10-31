export interface ImageDimensions {
  width: number
  height: number
  channels: number
}

export interface BoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface EdgeStatistics {
  total_edge_pixels: number
  edge_density: number
  boundary_edge_pixels: number
  filtered_background_edges: number
}

export interface ContourDescriptor {
  contour_id: number
  area: number
  perimeter: number
  bounding_box: BoundingBox
  aspect_ratio: number
  solidity: number
  extent: number
  is_internal: boolean
  hierarchy_level: number
}

export interface MainHarnessContour {
  area: number
  perimeter: number
  bounding_box: BoundingBox
  aspect_ratio: number
  solidity: number
  extent: number
  center_x: number
  center_y: number
}

export interface ContourInformation {
  total_contours: number
  external_contours_count: number
  internal_contours_count: number
  main_harness_contour?: MainHarnessContour | null
  significant_contours: ContourDescriptor[]
}

export interface EndpointCandidate {
  id: string
  x: number
  y: number
  tangent_angle_deg: number
  connection_degree: number
}

export interface JunctionCandidate {
  id: string
  x: number
  y: number
  branch_count: number
  is_simple_crossing: boolean
  branch_angles_deg: number[]
}

export interface BranchFeature {
  branch_id: string
  start_node: string
  end_node: string
  path_length_pixels: number
  straight_distance_pixels: number
  straightness_ratio: number
  orientation_deg: number
  mean_curvature: number
  max_bend_angle_deg: number
  compact_path: number[][]
}

export interface SkeletonFeatures {
  total_wire_length_pixels: number
  uncalibrated: boolean
  skeleton_pixel_count: number
  endpoint_candidates: EndpointCandidate[]
  junction_candidates: JunctionCandidate[]
  branches: BranchFeature[]
}

export interface CandidateRegionForPartId {
  candidate_type: 'TERMINAL_CANDIDATE' | 'JOINT_CANDIDATE' | 'CONNECTOR_CANDIDATE'
  associated_node_id: string
  bounding_box: BoundingBox
  local_area: number
  local_aspect_ratio: number
  note: string
}

export interface PairwiseDistance {
  from_node: string
  to_node: string
  distance_pixels: number
}

export interface GeometricFeatures {
  mean_branch_straightness: number
  max_bend_angle_deg: number
  total_detected_joints: number
  total_detected_terminals: number
  pairwise_feature_distances: PairwiseDistance[]
}

export interface FeatureVisualizations {
  original_preprocessed?: string | null
  edge_map?: string | null
  contour_visualization?: string | null
  skeleton_visualization?: string | null
  keypoint_junction_visualization?: string | null
  combined_overlay?: string | null
}

export interface FeatureExtractionResponse {
  image_dimensions: ImageDimensions
  edge_statistics: EdgeStatistics
  contour_information: ContourInformation
  skeleton_features: SkeletonFeatures
  candidate_regions_for_part_id: CandidateRegionForPartId[]
  geometric_features: GeometricFeatures
  visualizations?: FeatureVisualizations | null
  processing_time_ms: number
  warnings: string[]
  errors: string[]
}
