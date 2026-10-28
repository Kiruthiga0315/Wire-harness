export interface SegmentationImages {
  binary_mask: string
  contour_image: string
  skeleton_image: string
}

export interface SegmentationMetrics {
  harness_occupied_percentage: number
  contour_count: number
  otsu_threshold: number
  removed_component_count: number
  excluded_border_component_count: number
  image_width: number
  image_height: number
}

export interface SegmentationResponse {
  source_image: string
  method: string
  production_ready: boolean
  disclaimer: string
  metrics: SegmentationMetrics
  images: SegmentationImages
}

export interface GraphPoint {
  x: number
  y: number
}

export interface HarnessGraphResponse {
  source_image: string
  production_ready: boolean
  disclaimer: string
  metrics: {
    endpoint_count: number
    candidate_junction_pixel_count: number
    clustered_junction_count: number
    skeleton_pixel_count: number
    neighbour_connectivity: number
    junction_cluster_radius: number
    total_wire_length_pixels: number
    extracted_branch_length_pixels: number
    total_wire_length_cm?: number
    extracted_branch_length_cm?: number
    pixels_per_cm?: number
    unit?: string
    extracted_branch_count: number
    topology_terminal_count: number
    unresolved_segment_count: number
  }
  endpoints: GraphPoint[]
  junctions: GraphPoint[]
  measurements: {
    length_method: string
    orientation_convention: string
    branch_distance_definition: string
    nodes: Array<{
      node_id: string
      node_type: 'JUNCTION' | 'END_TERMINAL'
      x: number
      y: number
      branch_count: number
      branch_orientations: Array<{
        branch_id: string
        angle_degrees: number
      }>
    }>
    node_to_node_distances: Array<{
      branch_id: string
      source_node_id: string
      target_node_id: string
      path_length_pixels: number
      straight_distance_pixels: number
      orientation_degrees: number
    }>
    nearest_junction_to_terminal_distances: Array<{
      junction_node_id: string
      terminal_node_id: string
      path_distance_pixels: number
      straight_distance_pixels: number
    }>
    branch_to_branch_distances: Array<{
      junction_node_id: string
      first_branch_id: string
      second_branch_id: string
      via_junction_distance_pixels: number
      midpoint_straight_distance_pixels: number
      angular_separation_degrees: number
    }>
  }
  images: {
    skeleton_image: string
    graph_overlay: string
  }
}
