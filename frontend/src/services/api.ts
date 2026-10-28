import type { HealthResponse } from '../types/system'
import type { HarnessGraphResponse, SegmentationResponse } from '../types/engineering'
import type { CheckpointPayload, EngineeringCheckpoint } from '../types/checkpoint'
import type { MockInspectionResponse } from '../types/inspection'
import type { ColorInspectionResponse } from '../types/colorInspection'
import type { InspectionReportResponse } from '../types/report'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''
const DEMO_IMAGE_PATH = '/api/test-images/harness_sample_01.jpeg'

export const DEMO_IMAGE_URL = `${API_BASE_URL}${DEMO_IMAGE_PATH}`
export const ACTIVE_IMAGE_URL = `${API_BASE_URL}/api/test-images/active`
export const ACTIVE_CROPPED_IMAGE_URL = `${API_BASE_URL}/api/test-images/active/cropped`
export const GOLDEN_HARNESS_URL = `${API_BASE_URL}/api/golden-reference/images/golden_harness.png`
export const GOLDEN_SHEET_URL = `${API_BASE_URL}/api/golden-reference/images/measurement_sheet.png`

export interface ActiveImageMetadata {
  filename: string
  content_type: string
  width: number
  height: number
  size: number
  source: 'demo' | 'upload'
}

export async function uploadActiveImage(file: File | Blob, filename?: string): Promise<ActiveImageMetadata> {
  try {
    const formData = new FormData()
    const name = filename || (file instanceof File ? file.name : 'upload.png')
    formData.append('file', file, name)

    const response = await fetch(`${API_BASE_URL}/api/test-images/active`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      let message = 'Image upload failed.'
      try {
        const errorData = await response.json() as { detail?: string }
        if (errorData.detail) message = errorData.detail
      } catch {
        // Fallback message
      }
      throw new ApiError(message, response.status)
    }
    return (await response.json()) as ActiveImageMetadata
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to upload test image to inspection server.')
  }
}

export async function resetActiveImage(): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/api/test-images/active`, { method: 'DELETE' })
  } catch {
    // Graceful fallback
  }
}

export async function getActiveImageMetadata(signal?: AbortSignal): Promise<ActiveImageMetadata | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/test-images/active/metadata`, { signal })
    if (!response.ok) return null
    return (await response.json()) as ActiveImageMetadata
  } catch {
    return null
  }
}

export class ApiError extends Error {
  constructor(message: string, public readonly status?: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, { signal })
    if (!response.ok) {
      throw new ApiError('The inspection server returned an unexpected response.', response.status)
    }
    return (await response.json()) as HealthResponse
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    if (error instanceof ApiError) throw error
    throw new ApiError('Inspection server unavailable. Check that the backend is running.')
  }
}

export async function loadDemoImage(): Promise<Blob> {
  try {
    const response = await fetch(`${API_BASE_URL}${DEMO_IMAGE_PATH}`, { cache: 'no-store' })
    if (!response.ok) {
      const detail = response.status === 404
        ? 'The demo image was not found in data/test_images.'
        : 'The inspection server could not load the demo image.'
      throw new ApiError(detail, response.status)
    }
    const image = await response.blob()
    if (!image.type.startsWith('image/')) {
      throw new ApiError('The demo file is not a supported image.')
    }
    return image
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Demo image unavailable. Check that the backend is running.')
  }
}

export async function runDemoSegmentation(signal?: AbortSignal): Promise<SegmentationResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/engineering/segmentation/demo`, {
      method: 'POST',
      signal,
    })
    if (!response.ok) {
      const detail = response.status === 404
        ? 'The configured harness test image is missing.'
        : 'The experimental segmentation process failed.'
      throw new ApiError(detail, response.status)
    }
    return (await response.json()) as SegmentationResponse
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    if (error instanceof ApiError) throw error
    throw new ApiError('Engineering processing unavailable. Check that the backend is running.')
  }
}

export async function runHarnessGraphAnalysis(): Promise<HarnessGraphResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/engineering/harness-graph/demo`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new ApiError('Experimental harness graph analysis failed.', response.status)
    }
    return await response.json() as HarnessGraphResponse
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Harness graph service unavailable. Check that the backend is running.')
  }
}

const checkpointPath = (modelId: string) => `${API_BASE_URL}/api/models/${encodeURIComponent(modelId)}/checkpoints`

async function checkpointRequest<T>(url: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(url, init)
    if (!response.ok) {
      let message = 'Checkpoint operation failed.'
      try {
        const payload = await response.json() as { detail?: string }
        if (payload.detail) message = payload.detail
      } catch {
        // Preserve the operator-friendly fallback message.
      }
      throw new ApiError(message, response.status)
    }
    return response.status === 204 ? undefined as T : await response.json() as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Checkpoint database unavailable. Check that the backend is running.')
  }
}

export function getCheckpoints(modelId: string): Promise<EngineeringCheckpoint[]> {
  return checkpointRequest<EngineeringCheckpoint[]>(checkpointPath(modelId))
}

export function createCheckpoint(modelId: string, payload: CheckpointPayload): Promise<EngineeringCheckpoint> {
  return checkpointRequest<EngineeringCheckpoint>(checkpointPath(modelId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function updateCheckpoint(modelId: string, checkpointId: string, payload: CheckpointPayload): Promise<EngineeringCheckpoint> {
  return checkpointRequest<EngineeringCheckpoint>(`${checkpointPath(modelId)}/${encodeURIComponent(checkpointId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export function deleteCheckpoint(modelId: string, checkpointId: string): Promise<void> {
  return checkpointRequest<void>(`${checkpointPath(modelId)}/${encodeURIComponent(checkpointId)}`, {
    method: 'DELETE',
  })
}

export async function runMockInspection(modelId: string): Promise<MockInspectionResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/inspections/demo/process`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId }),
    })
    if (!response.ok) {
      let message = 'Mock inspection processing failed.'
      try {
        const payload = await response.json() as { detail?: string }
        if (payload.detail) message = payload.detail
      } catch {
        // Preserve the operator-friendly fallback message.
      }
      throw new ApiError(message, response.status)
    }
    return await response.json() as MockInspectionResponse
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Inspection service unavailable. Check that the backend is running.')
  }
}

export async function runColorInspection(
  modelId: string,
  checkpointId: string,
  debug: boolean,
): Promise<ColorInspectionResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/engineering/color-inspection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_id: modelId, checkpoint_id: checkpointId, debug }),
    })
    if (!response.ok) {
      let message = 'Colour inspection failed.'
      try {
        const payload = await response.json() as { detail?: string }
        if (payload.detail) message = payload.detail
      } catch {
        // Preserve the fallback message.
      }
      throw new ApiError(message, response.status)
    }
    return await response.json() as ColorInspectionResponse
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Colour inspection service unavailable. Check that the backend is running.')
  }
}

export async function getDemoReport(signal?: AbortSignal): Promise<InspectionReportResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/reports/demo`, { signal, cache: 'no-store' })
    if (!response.ok) {
      throw new ApiError('The inspection report could not be generated.', response.status)
    }
    return await response.json() as InspectionReportResponse
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    if (error instanceof ApiError) throw error
    throw new ApiError('Reporting service unavailable. Check that the backend is running.')
  }
}

export async function downloadDemoReportCsv(): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/reports/demo/export.csv`, { cache: 'no-store' })
    if (!response.ok) {
      throw new ApiError('CSV export could not be generated.', response.status)
    }
    const blob = await response.blob()
    const disposition = response.headers.get('Content-Disposition') ?? ''
    const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? 'wire-harness-report.csv'
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('CSV export unavailable. Check that the backend is running.')
  }
}

export async function getGoldenReference(signal?: AbortSignal): Promise<import('../types/goldenReference').GoldenReferenceConfig> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference`, { signal })
    if (!response.ok) {
      throw new ApiError('Could not load golden reference configuration.', response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenReferenceConfig
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    if (error instanceof ApiError) throw error
    throw new ApiError('Golden reference service unavailable.')
  }
}

export async function updateGoldenCheckpoint(
  checkpointId: string,
  payload: Partial<import('../types/goldenReference').GoldenCheckpoint>,
): Promise<import('../types/goldenReference').GoldenCheckpoint> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/checkpoints/${encodeURIComponent(checkpointId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new ApiError(`Failed to update checkpoint ${checkpointId}`, response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenCheckpoint
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to communicate with golden reference service.')
  }
}

export async function addGoldenCheckpoint(
  payload: import('../types/goldenReference').GoldenCheckpoint,
): Promise<import('../types/goldenReference').GoldenCheckpoint> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/checkpoints`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      throw new ApiError('Failed to create checkpoint', response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenCheckpoint
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to create golden checkpoint.')
  }
}

export async function deleteGoldenCheckpoint(checkpointId: string): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/checkpoints/${encodeURIComponent(checkpointId)}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      throw new ApiError(`Failed to delete checkpoint ${checkpointId}`, response.status)
    }
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to delete golden checkpoint.')
  }
}

export async function updateGoldenCalibration(
  calibration: import('../types/goldenReference').GoldenCalibration,
): Promise<import('../types/goldenReference').GoldenCalibration> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/calibration`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(calibration),
    })
    if (!response.ok) {
      throw new ApiError('Failed to update calibration', response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenCalibration
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to save calibration.')
  }
}

export async function resetGoldenReference(): Promise<import('../types/goldenReference').GoldenReferenceConfig> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/reset`, {
      method: 'POST',
    })
    if (!response.ok) {
      throw new ApiError('Failed to reset golden reference', response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenReferenceConfig
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to reset golden reference.')
  }
}

export async function runGoldenInspection(pixelsPerMm?: number): Promise<import('../types/goldenReference').GoldenInspectionResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/inspect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ use_active_image: true, pixels_per_mm: pixelsPerMm }),
    })
    if (!response.ok) {
      let detail = 'Golden reference inspection failed.'
      try {
        const err = await response.json() as { detail?: string }
        if (err.detail) detail = err.detail
      } catch {
        // Fallback
      }
      throw new ApiError(detail, response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenInspectionResponse
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Inspection service error.')
  }
}

export async function runUploadedGoldenInspection(file: File): Promise<import('../types/goldenReference').GoldenInspectionResponse> {
  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch(`${API_BASE_URL}/api/golden-reference/inspect-upload`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      let detail = 'Image inspection failed.'
      try {
        const err = await response.json() as { detail?: string }
        if (err.detail) detail = err.detail
      } catch {
        // Fallback
      }
      throw new ApiError(detail, response.status)
    }
    return (await response.json()) as import('../types/goldenReference').GoldenInspectionResponse
  } catch (error) {
    if (error instanceof ApiError) throw error
    throw new ApiError('Failed to upload and inspect against golden reference.')
  }
}
