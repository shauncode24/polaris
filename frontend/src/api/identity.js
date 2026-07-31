// frontend/src/api/identity.js
import { API_BASE_URL } from './client'

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

export function getEngineeringIdentity(token) {
  return fetch(`${API_BASE_URL}/identity`, { headers: authHeaders(token) }).then(handle)
}

export function refreshEngineeringIdentity(token) {
  return fetch(`${API_BASE_URL}/identity/refresh`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function getWeeklyBrief(token) {
  return fetch(`${API_BASE_URL}/identity/weekly-brief`, { headers: authHeaders(token) }).then(handle)
}

export function refreshWeeklyBrief(token) {
  return fetch(`${API_BASE_URL}/identity/weekly-brief/refresh`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}