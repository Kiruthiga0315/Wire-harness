export type CheckpointInspectionStatus = 'PASS' | 'NG'
export type InspectionState = 'READY' | 'CAPTURING' | 'PROCESSING' | 'PASS' | 'NG' | 'ERROR'

export interface InspectionBoundingBox {
  x: number
  y: number
  width: number
  height: number
}

export interface MockCheckpointResult {
  checkpoint_id: string
  checkpoint_name: string
  category: string
  inspection_type: string
  expected_value: string | null
  actual_value: string | null
  tolerance: number | null
  deviation: string | null
  confidence: number
  status: CheckpointInspectionStatus
  status_reason: string
  bounding_box: InspectionBoundingBox
}

export interface MockInspectionResponse {
  inspection_id: string
  model_id: string
  model_name: string
  state: 'PASS' | 'NG'
  total_checkpoints: number
  passed: number
  failed: number
  warnings: number
  cycle_time_seconds: number
  timestamp: string
  results: MockCheckpointResult[]
}
