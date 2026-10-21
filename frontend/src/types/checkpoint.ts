export interface EngineeringCheckpoint {
  id: number
  checkpoint_id: string
  model_id: string
  checkpoint_name: string
  category: string
  inspection_type: string
  expected_value: string | null
  tolerance: number | null
  reference_x: number
  reference_y: number
  roi_width: number
  roi_height: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface CheckpointPayload {
  checkpoint_name: string
  category: string
  inspection_type: string
  expected_value: string | null
  tolerance: number | null
  reference_x: number
  reference_y: number
  roi_width: number
  roi_height: number
  enabled: boolean
}
