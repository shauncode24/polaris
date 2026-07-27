// frontend/src/api/resume.js
import { API_BASE_URL } from './client'

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((typeof data.detail === 'string' && data.detail) || 'Something went wrong.')
  }
  return data
}

export function getResumeWorkspace(token) {
  return fetch(`${API_BASE_URL}/resume/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getResumeDownloadUrl() {
  return `${API_BASE_URL}/resume/download`
}

export function uploadResume(file, token) {
  const formData = new FormData()
  formData.append('file', file)
  return fetch(`${API_BASE_URL}/resume/upload`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function runResumeReview(token) {
  return fetch(`${API_BASE_URL}/resume/review`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}
