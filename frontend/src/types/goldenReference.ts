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
}
