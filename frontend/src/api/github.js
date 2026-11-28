// frontend/src/api/github.js
import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

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
  return authFetch(`${API_BASE_URL}/github/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function runGithubPortfolioReview(token) {
  return apiFetch(`${API_BASE_URL}/github/review`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}