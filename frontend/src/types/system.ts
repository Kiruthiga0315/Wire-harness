export type HealthStatus = 'healthy' | 'degraded' | 'offline'

export interface HealthResponse {
  status: HealthStatus
  service: string
  version: string
  environment: string
  database: string
  ai_mode: string
  camera_mode: string
  timestamp: string
}
