// frontend/src/api/github.js
import { API_BASE_URL } from './client'

export { syncGithub } from './profile'

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((typeof data.detail === 'string' && data.detail) || data.reason || 'Something went wrong.')
  }
  return data
}

export function getGithubWorkspace(token) {
  return fetch(`${API_BASE_URL}/github/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}