import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth'
import { endSession, onSessionChange, renewSession } from '../api/session'

const AuthContext = createContext(null)
// Where week-long tokens used to be kept.
const OLD_TOKEN_KEY = 'polaris-token'

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  // True when the server couldn't say whether this browser is signed in.
  const [unreachable, setUnreachable] = useState(false)

  const restore = useCallback(async () => {
    setLoading(true)
    setUnreachable(false)
    try {
      await renewSession()
    } catch {
      setUnreachable(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    localStorage.removeItem(OLD_TOKEN_KEY)
    const stopListening = onSessionChange(setSession)
    restore()
    return stopListening
  }, [restore])

  const value = {
    // Changes only when someone signs in or out. Requests made with it are sent
    // with the current access token (see `authFetch`).
    token: session?.access_token ?? null,
    user: session?.user ?? null,
    loading,
    unreachable,
    retry: restore,
    register: authApi.register,
    login: authApi.login,
    loginWithGoogle: authApi.googleAuth,
    logout: endSession,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
