import { useEffect, useState } from 'react'
import { checkHealth } from '../api/client'

const POLL_INTERVAL_MS = 30000

// Pings the FastAPI /health endpoint so the UI can honestly reflect
// whether the backend is actually reachable, instead of hardcoding
// a "connected" label in the footer.
export function useBackendStatus() {
  const [status, setStatus] = useState('checking') // 'checking' | 'online' | 'offline'

  useEffect(() => {
    let cancelled = false

    async function ping() {
      try {
        await checkHealth()
        if (!cancelled) setStatus('online')
      } catch {
        if (!cancelled) setStatus('offline')
      }
    }

    ping()
    const interval = setInterval(ping, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return status
}
