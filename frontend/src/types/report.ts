import type { MockCheckpointResult } from './inspection'
import type {
  ColoredTapeSummary,
  TerminalIdentification,
  TopologySummary,
} from './goldenReference'

export interface ReportBranchMeasurement {
  branch_id: string
  source_node_id: string
  target_node_id: string
  path_length_pixels: number
  straight_distance_pixels: number
  orientation_degrees: number
  path_length_cm?: number
  straight_distance_cm?: number
  unit?: string
}

export interface StickerFieldData {
  harness_code: string | null
  part_number: string | null
  description: string | null
  drawing_number: string | null
  serial_number: string | null
  barcode_payload: string | null
  supplier: string | null
  batch_code: string | null
}

export interface StickerInspectionReport {
  present: boolean
  status: 'PRESENT' | 'NOT_PRESENT'
  notification: string
  confidence: number
  fields: StickerFieldData
  thumbnail: string | null
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
  total_wire_length_cm?: number
  pixels_per_cm?: number
  unit?: string
  extracted_branch_count: number
  clustered_junction_count: number
  terminal_count: number
  spine_node_count?: number
  unresolved_segment_count: number
  annotated_image: string
  checkpoint_results: MockCheckpointResult[]
  branch_measurements: ReportBranchMeasurement[]
  sticker_inspection: StickerInspectionReport
  colored_tapes?: ColoredTapeSummary
  topology_summary?: TopologySummary
  terminal_identifications?: TerminalIdentification[]
  disclaimer: string
}
