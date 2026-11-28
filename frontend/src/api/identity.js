// frontend/src/api/identity.js
import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((typeof data.detail === 'string' && data.detail) || data.reason || 'Something went wrong.')
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function getEngineeringIdentity(token) {
  const response = await authFetch(`${API_BASE_URL}/identity`, {
    headers: authHeaders(token),
  })
  if (response.status === 404) return null
  if (!response.ok) return null
  return response.json().catch(() => null)
}

export function refreshEngineeringIdentity(token) {
  return apiFetch(`${API_BASE_URL}/identity/refresh`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function getIdentityHistory(token, limit = 10) {
  return authFetch(`${API_BASE_URL}/identity/history?limit=${limit}`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getWeeklyBrief(token) {
  return authFetch(`${API_BASE_URL}/identity/weekly-brief`, { headers: authHeaders(token) }).then(handle)
}

export function refreshWeeklyBrief(token) {
  return apiFetch(`${API_BASE_URL}/identity/weekly-brief/refresh`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}