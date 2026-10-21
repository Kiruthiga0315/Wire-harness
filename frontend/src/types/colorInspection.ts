export interface ColourVector {
  channel_1: number
  channel_2: number
  channel_3: number
}

export interface ColorInspectionResponse {
  model_id: string
  checkpoint_id: string
  checkpoint_name: string
  expected_colour: string
  detected_colour: string
  mean_hsv: ColourVector
  mean_lab: ColourVector
  confidence: number
  status: 'PASS' | 'NG'
  roi: { x: number; y: number; width: number; height: number }
  debug_roi_image: string | null
  production_ready: boolean
  disclaimer: string
}
