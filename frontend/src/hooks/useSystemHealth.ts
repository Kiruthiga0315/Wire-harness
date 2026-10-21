import { useEffect, useState } from 'react'
import { getHealth } from '../services/api'
import type { HealthResponse } from '../types/system'

interface SystemHealthState {
  health: HealthResponse | null
  loading: boolean
  error: string | null
}

export function useSystemHealth(): SystemHealthState {
  const [state, setState] = useState<SystemHealthState>({
    health: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((health) => setState({ health, loading: false, error: null }))
      .catch((error: Error) => {
        if (error.name !== 'AbortError') {
          setState({ health: null, loading: false, error: error.message })
        }
      })
    return () => controller.abort()
  }, [])

  return state
}
