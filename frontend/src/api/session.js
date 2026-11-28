// The signed-in session. The access token is short-lived and kept only in
// memory. New ones are got with the refresh token, an httpOnly cookie that
// scripts can't read.
import { API_BASE_URL } from './config'

// Set by signing out, cleared by signing in. While set, the cookie isn't used,
// even if the server couldn't be told to end it.
const SIGNED_OUT_KEY = 'polaris-signed-out'
const UNREACHABLE = "Couldn't check your sign-in. Try again shortly."

let current = null // { access_token, user } while signed in
let renewal = null
const listeners = new Set()

// Calls `listener` with the session now, and whenever someone signs in or out.
// Renewing the token of the same user isn't announced: pages would reload.
export function onSessionChange(listener) {
  listeners.add(listener)
  listener(current)
  return () => listeners.delete(listener)
}

function adopt(session) {
  const changed = current?.user.id !== session?.user.id
  current = session
  if (changed) listeners.forEach((listener) => listener(session))
}

// One session request at a time, across tabs where the browser allows it: they
// share the cookie, and each reply replaces it.
let queue = Promise.resolve()
function inTurn(task) {
  if (navigator.locks) return navigator.locks.request('polaris-session', task)
  const result = queue.then(task)
  queue = result.catch(() => {})
  return result
}

// A POST to /auth/ that may read or set the cookie.
export function postAuth(path, body) {
  return fetch(`${API_BASE_URL}/auth/${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
}

// `request` signs in and resolves to the new session.
export function startSession(request) {
  return inTurn(async () => {
    const session = await request()
    localStorage.removeItem(SIGNED_OUT_KEY)
    adopt(session)
    return session
  })
}

async function revoke() {
  try {
    await postAuth('logout')
  } catch {
    // Tried again the next time a session would be renewed.
  }
}

export function endSession() {
  localStorage.setItem(SIGNED_OUT_KEY, '1')
  adopt(null)
  return inTurn(revoke)
}

async function renew() {
  if (localStorage.getItem(SIGNED_OUT_KEY)) {
    await revoke()
    adopt(null)
    return null
  }
  const response = await postAuth('refresh')
  if (response.status === 401) {
    adopt(null)
    return null
  }
  if (!response.ok) throw new Error(UNREACHABLE)
  const session = await response.json()
  if (localStorage.getItem(SIGNED_OUT_KEY)) return null // signed out meanwhile
  if (current && current.user.id !== session.user.id) {
    // Someone else signed in from another tab: nothing on this page is theirs.
    window.location.reload()
    return null
  }
  adopt(session)
  return session
}

// Resolves to the session, or null when there is none (any more). Rejects when
// the server couldn't say, which leaves things as they were.
export function renewSession() {
  renewal ??= inTurn(renew).finally(() => {
    renewal = null
  })
  return renewal
}

// Signing out in one tab signs the others out too.
window.addEventListener('storage', (event) => {
  if (event.key === SIGNED_OUT_KEY && event.newValue) adopt(null)
})

function withToken(options, token) {
  return { ...options, headers: { ...options.headers, Authorization: `Bearer ${token}` } }
}

// `fetch` for requests made as the signed-in user. Pages hold the token from
// when the user signed in; it is swapped here for the current one, which is
// renewed once the server stops accepting it.
export async function authFetch(url, options = {}) {
  const userId = current?.user.id
  if (!options.headers?.Authorization || !userId) return fetch(url, options)

  const sent = current.access_token
  const response = await fetch(url, withToken(options, sent))
  if (response.status !== 401) return response

  // Another request may have renewed it already.
  const session = current?.access_token !== sent ? current : await renewSession()
  // Not sent again if the session ended, or is someone else's now.
  if (session?.user.id !== userId) return response
  // The refused request did nothing, so sending it again is safe.
  return fetch(url, withToken(options, session.access_token))
}
