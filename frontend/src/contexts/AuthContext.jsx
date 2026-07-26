import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import * as authApi from '../api/auth'

const AuthContext = createContext(null)
const TOKEN_KEY = 'polaris-token'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const loadUser = useCallback(async (activeToken) => {
    if (!activeToken) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await authApi.fetchMe(activeToken)
      setUser(me)
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUser(token)
  }, [token, loadUser])

  function applySession(session) {
    localStorage.setItem(TOKEN_KEY, session.access_token)
    setToken(session.access_token)
    setUser(session.user)
  }

  async function register(payload) {
    const session = await authApi.register(payload)
    applySession(session)
    return session
  }

  async function login(payload) {
    const session = await authApi.login(payload)
    applySession(session)
    return session
  }

  async function loginWithGoogle(credential) {
    const session = await authApi.googleAuth(credential)
    applySession(session)
    return session
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, loading, register, login, loginWithGoogle, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}