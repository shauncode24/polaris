// frontend/src/api/linkedin.js
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

export function ingestLinkedInProfile(token, rawText) {
  return fetch(`${API_BASE_URL}/linkedin/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ raw_text: rawText }),
  }).then(handle)
}

export function getLinkedInWorkspace(token) {
  return fetch(`${API_BASE_URL}/linkedin/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}