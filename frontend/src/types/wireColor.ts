export interface WireColorVector {
  channel_1: number
  channel_2: number
  channel_3: number
}

export interface WireSectionROI {
  section_id: string
  color_id: 'dark_blue' | 'grey' | 'black' | 'green'
  color_name: string
  status: 'Detected' | 'Uncertain' | 'Not detected'
  x: number
  y: number
  width: number
  height: number
  pixel_count: number
  percentage: number
  confidence: number
  mean_hsv?: WireColorVector | null
  mean_lab?: WireColorVector | null
  cropped_image: string
  original_crop?: string | null
  overlay_color_hex: string
  description: string
}

export interface WireColorDetail {
  color_id: 'dark_blue' | 'grey' | 'black' | 'green'
  name: string
  status: 'Detected' | 'Uncertain' | 'Not detected'
  detected: boolean
  pixel_count: number
  percentage: number
  confidence: number
  mean_hsv?: WireColorVector | null
  mean_lab?: WireColorVector | null
  regions_count: number
  overlay_color_hex: string
  description: string
}

export interface WireColorIdentificationResponse {
  source_image: string
  image_width: number
  image_height: number
  analyzed_wire_pixels: number
  total_harness_pixels: number
  colors: WireColorDetail[]
  sections: WireSectionROI[]
  overlay_image: string
  original_image: string
  color_masks: Record<string, string>
  production_ready: boolean
  method: string
  disclaimer: string
}
