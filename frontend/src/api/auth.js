import { API_BASE_URL } from './client'

// A refused field arrives as a list of problems; other errors as plain text.
function errorMessage(detail) {
  if (Array.isArray(detail)) return detail[0]?.msg?.replace(/^Value error, /, '')
  return typeof detail === 'string' ? detail : undefined
}

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(errorMessage(data.detail) || 'Something went wrong. Please try again.')
    error.status = response.status
    throw error
  }
  return data
}

export function register({ firstName, lastName, email, password }) {
  return fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ first_name: firstName, last_name: lastName, email, password }),
  }).then(handle)
}

export function login({ email, password }) {
  return fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  }).then(handle)
}

export function googleAuth(credential) {
  return fetch(`${API_BASE_URL}/auth/google`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  }).then(handle)
}

export function fetchMe(token) {
  return fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then(handle)
}