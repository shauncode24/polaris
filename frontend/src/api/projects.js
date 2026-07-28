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

export function listProjects(token) {
  return fetch(`${API_BASE_URL}/projects`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getProjectsInsights(token) {
  return fetch(`${API_BASE_URL}/projects/insights`, {
    headers: authHeaders(token),
  }).then(handle)
}