export interface ColourVector {
  channel_1: number
  channel_2: number
  channel_3: number
}

export interface TapeDetectionItem {
  region_id: string
  detected_color: string
  bbox: number[]
  center: number[]
  area: number
  width: number
  height: number
  confidence: number
  status: string
  branch_id: string
  mean_hsv?: ColourVector | null
  mean_lab?: ColourVector | null
}

export interface WireDetectionItem {
  region_id: string
  detected_color: string
  bbox: number[]
  center: number[]
  area: number
  width: number
  height: number
  branch_id: string
  confidence: number
  status: string
  mean_hsv?: ColourVector | null
  mean_lab?: ColourVector | null
}

export interface ColourSummary {
  green_tape: number
  dark_blue_tape: number
  gray_tape: number
  wire_regions: number
  uncertain_detections: number
}

export interface VerificationResult {
  status: 'PASS' | 'NG' | 'UNCERTAIN' | 'NOT_CONFIGURED'
  message: string
  details: Record<string, unknown>[]
}

export interface ColourIdentificationResponse {
  success: boolean
  inspection_id: string
  image_width: number
  image_height: number
  colour_summary: ColourSummary
  tape_detections: TapeDetectionItem[]
  wire_detections: WireDetectionItem[]
  verification: VerificationResult
  overlay_image: string
  original_image: string
  processing_time_ms: number
  method: string
  disclaimer: string
  production_ready: boolean
}
