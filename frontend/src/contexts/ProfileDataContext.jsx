/* @refresh reload */

import { createContext, useContext, useEffect, useState } from 'react'
import { useAuth } from './AuthContext'

const ProfileDataContext = createContext(null)

function storageKey(userId) {
  return `polaris-profile-ingestion:${userId || 'anonymous'}`
}

function loadInitial(userId) {
  if (typeof window === 'undefined') return {}
  try {
    const raw = localStorage.getItem(storageKey(userId))
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export function ProfileDataProvider({ children }) {
  const { user } = useAuth()
  const userId = user?.id
  const [results, setResults] = useState(() => loadInitial(userId))

  useEffect(() => {
    setResults(loadInitial(userId))
  }, [userId])

  useEffect(() => {
    try {
      localStorage.setItem(storageKey(userId), JSON.stringify(results))
    } catch {
      // localStorage full/unavailable — non-fatal
    }
  }, [results, userId])

  function setResult(key, value) {
    setResults((prev) => ({ ...prev, [key]: value }))
  }

  function clearResults() {
    setResults({})
    localStorage.removeItem(storageKey(userId))
  }

  return (
    <ProfileDataContext.Provider value={{ results, setResult, clearResults }}>
      {children}
    </ProfileDataContext.Provider>
  )
}

export function useProfileData() {
  const ctx = useContext(ProfileDataContext)
  if (!ctx) throw new Error('useProfileData must be used within a ProfileDataProvider')
  return ctx
}