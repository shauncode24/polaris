// frontend/src/contexts/PolarisIdentityContext.jsx
//
// Shared identity context — Phase 3 consolidation.
//
// Before Phase 3, each page that needed identity data (IdentityPage,
// DashboardPage, etc.) called getEngineeringIdentity() independently
// on mount. This meant:
//   - Multiple concurrent fetches for the same data when multiple
//     components mounted simultaneously.
//   - No shared invalidation: refreshing identity on one page left
//     other pages stale until their own next mount.
//   - No single place to reason about "does the identity exist yet?"
//
// PolarisIdentityProvider wraps the authenticated part of the app and
// makes the current identity available to any component via the
// usePolarisIdentity() hook.
//
// Key design decisions:
//   - Fetches on mount when token is available; re-fetches when token
//     changes (login/logout transitions).
//   - Exposes a refresh() function so a POST /identity/refresh call on
//     IdentityPage can push the updated identity to all consumers
//     without a page reload.
//   - Does NOT auto-poll — identity changes only on deliberate user
//     actions (resume upload, sync, manual refresh). On-demand fetch is
//     the right model here.
//   - Clears identity immediately on logout (user change to null) so
//     no stale data bleeds across sessions.

import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'
import { getEngineeringIdentity, refreshEngineeringIdentity } from '../api/identity'

const PolarisIdentityContext = createContext(null)

export function PolarisIdentityProvider({ children }) {
  const { token, user } = useAuth()

  const [identity, setIdentity] = useState(null)
  // null = first load not yet attempted; true = loading; false = done
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Fetch the latest identity from the server (read-only, no LLM).
  const fetchIdentity = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const data = await getEngineeringIdentity(token)
      setIdentity(data) // null when 404 (no identity generated yet)
    } catch (err) {
      console.error('[PolarisIdentity] Failed to load identity:', err)
      setError(err)
    } finally {
      setLoading(false)
    }
  }, [token])

  // Trigger the LLM rebuild (POST /identity/refresh), then update state.
  // Called by IdentityPage after a user-initiated refresh so all consumers
  // immediately see the new snapshot.
  const refresh = useCallback(async () => {
    if (!token) return
    setLoading(true)
    setError(null)
    try {
      const data = await refreshEngineeringIdentity(token)
      setIdentity(data)
      return data
    } catch (err) {
      console.error('[PolarisIdentity] Refresh failed:', err)
      setError(err)
      throw err
    } finally {
      setLoading(false)
    }
  }, [token])

  // Fetch on first mount and whenever the auth token changes.
  useEffect(() => {
    fetchIdentity()
  }, [fetchIdentity])

  // Clear identity immediately on logout to prevent cross-session bleed.
  useEffect(() => {
    if (!user) {
      setIdentity(null)
      setError(null)
    }
  }, [user])

  return (
    <PolarisIdentityContext.Provider
      value={{
        identity,   // EngineeringIdentityReport | null
        loading,    // boolean — true during any in-flight fetch
        error,      // Error | null
        refetch: fetchIdentity,  // re-fetch without LLM rebuild
        refresh,    // trigger POST /identity/refresh + update state
      }}
    >
      {children}
    </PolarisIdentityContext.Provider>
  )
}

export function usePolarisIdentity() {
  const ctx = useContext(PolarisIdentityContext)
  if (!ctx) {
    throw new Error('usePolarisIdentity must be used inside <PolarisIdentityProvider>')
  }
  return ctx
}
