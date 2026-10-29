export interface GoldenCalibration {
  calibrated: boolean
  method: string
  known_distance_mm: number
  pixel_distance: number
  pixels_per_mm: number
  endpoint1?: { x: number; y: number }
  endpoint2?: { x: number; y: number }
  unit: string
}

export interface SpecificationSummary {
  total_checkpoints?: number
  total_terminals: number
  total_junctions?: number
  total_nodes: number
  unit: string
  source_unit: string
  unconfirmed_count: number
  confirmed_count: number
}

export interface GoldenCheckpoint {
  checkpoint_id: string
  type: 'terminal' | 'junction' | 'node_distance' | 'branch'
  terminal_id: string | null
  node_id: string | null
  branch_id: string | null
  measurement_type: string
  expected_value: number | null
  unit: string
  tolerance: number | null
  reference_x: number
  reference_y: number
  roi_width: number
  roi_height: number
  confidence: number
  status: 'CONFIRMED' | 'NEEDS_CONFIRMATION' | 'REVIEW'
  notes: string
}

export interface GoldenReferenceConfig {
  model_id: string
  model_name: string
  golden_image: string
  measurement_sheet: string
  image_width: number
  image_height: number
  specification_summary: SpecificationSummary
  calibration: GoldenCalibration
  checkpoints: GoldenCheckpoint[]
}

export interface CheckpointInspectionResult {
  checkpoint_id: string
  type: string
  terminal_id: string | null
  node_id: string | null
  branch_id: string | null
  measurement_type: string
  expected_value: number | null
  detected_value: number | null
  unit: string
  tolerance: number | null
  deviation: number | null
  percentage_deviation: number | null
  status: 'PASS' | 'FAIL' | 'REVIEW'
  confidence: number
  message: string
  golden_coord: [number, number]
  test_coord: [number, number]
  roi_bbox: [number, number, number, number]
}

export interface TopologyFeatureLocation {
  id?: string
  terminal_id?: string
  junction_id?: string
  node_id?: string
  checkpoint_id?: string
  type?: string
  x?: number
  y?: number
  location_x?: number
  location_y?: number
  golden_x?: number
  golden_y?: number
  status?: string
  label?: string
}

export interface JunctionTerminalLength {
  junction_id: string
  terminal_id: string
  expected_mm: number | null
  detected_mm: number | null
  expected_cm: number | null
  detected_cm: number | null
  tolerance_mm: number | null
  deviation_mm: number | null
  status: string
}

export interface JunctionJunctionLength {
  from_junction: string
  to_junction: string
  expected_mm: number | null
  detected_mm: number | null
  expected_cm: number | null
  detected_cm: number | null
  tolerance_mm: number | null
  deviation_mm: number | null
  status: string
}

export interface NodeNodeLength {
  from_node: string
  to_node: string
  expected_mm: number | null
  detected_mm: number | null
  expected_cm: number | null
  detected_cm: number | null
  tolerance_mm: number | null
  deviation_mm: number | null
  status: string
}

export interface TopologySummary {
  terminal_count: number
  junction_count: number
  branch_count: number
  node_count: number
  terminals: TopologyFeatureLocation[]
  junctions: TopologyFeatureLocation[]
  nodes: TopologyFeatureLocation[]
  junction_to_terminal_lengths: JunctionTerminalLength[]
  junction_to_junction_lengths: JunctionJunctionLength[]
  node_to_node_lengths: NodeNodeLength[]
}

export interface ColoredTapeInfo {
  color_id: string
  name: string
  detected: boolean
  status: string
  confidence: number
  percentage: number
  color_hex: string
  description: string
}

export interface ColoredTapeSummary {
  green?: ColoredTapeInfo
  dark_blue?: ColoredTapeInfo
  grey?: ColoredTapeInfo
  black?: ColoredTapeInfo
  all_colors?: ColoredTapeInfo[]
}

export interface StickerSummary {
  present: boolean
  status: 'PRESENT' | 'NOT_PRESENT'
  confidence: number
  notification: string
  fields: {
    harness_code?: string | null
    part_number?: string | null
    description?: string | null
    drawing_number?: string | null
    serial_number?: string | null
    barcode_payload?: string | null
    supplier?: string | null
    batch_code?: string | null
  }
  thumbnail_data_url?: string | null
}

export interface TerminalIdentification {
  terminal_id: string
  checkpoint_id: string
  location_x: number
  location_y: number
  golden_x: number
  golden_y: number
  expected_mm: number | null
  detected_mm: number | null
  expected_cm?: number | null
  detected_cm?: number | null
  deviation_mm: number | null
  tolerance_mm: number | null
  status: string
  parent_junction: string
  confidence: number
  label?: string
}

export interface GoldenInspectionResponse {
  inspection_id: string
  timestamp: string
  overall_status: 'PASS' | 'FAIL' | 'REVIEW'
  total_checkpoints: number
  passed_count: number
  failed_count: number
  review_count: number
  calibrated: boolean
  pixels_per_mm: number
  alignment_confidence: number
  marked_image_data_url: string
  results: CheckpointInspectionResult[]
  summary_notes: string[]
  topology_summary?: TopologySummary
  colored_tapes?: ColoredTapeSummary
  sticker?: StickerSummary
  terminal_identifications?: TerminalIdentification[]
}
