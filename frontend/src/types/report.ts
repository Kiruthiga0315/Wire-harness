import type { MockCheckpointResult } from './inspection'

export interface ReportBranchMeasurement {
  branch_id: string
  source_node_id: string
  target_node_id: string
  path_length_pixels: number
  straight_distance_pixels: number
  orientation_degrees: number
}

export interface InspectionReportResponse {
  report_id: string
  inspection_id: string
  generated_at: string
  model_id: string
  model_name: string
  revision: string
  work_order: string
  barcode: string
  operator: string
  source_image: string
  overall_result: 'PASS' | 'NG'
  total_checkpoints: number
  passed: number
  failed: number
  warnings: number
  cycle_time_seconds: number
  total_wire_length_pixels: number
  extracted_branch_count: number
  clustered_junction_count: number
  terminal_count: number
  unresolved_segment_count: number
  annotated_image: string
  checkpoint_results: MockCheckpointResult[]
  branch_measurements: ReportBranchMeasurement[]
  disclaimer: string
}
