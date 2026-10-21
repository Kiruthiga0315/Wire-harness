import type { HealthResponse } from '../types/system'
import type { HarnessGraphResponse, SegmentationResponse } from '../types/engineering'
import type { CheckpointPayload, EngineeringCheckpoint } from '../types/checkpoint'
import type { MockInspectionResponse } from '../types/inspection'
import type { ColorInspectionResponse } from '../types/colorInspection'
import type { InspectionReportResponse } from '../types/report'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
const DEMO_IMAGE_PATH = '/api/test-images/harness_sample_01.jpeg'

export const DEMO_IMAGE_URL = `${API_BASE_URL}${DEMO_IMAGE_PATH}`

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
