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

export function runResumeAnalysis(token, jobDescriptionId = null) {
  const url = new URL(`${API_BASE_URL}/resume/analyze`)
  if (jobDescriptionId) {
    url.searchParams.append('job_description_id', jobDescriptionId)
  }
  return fetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function getResumeCoherence(token, targetRole = null) {
  const url = new URL(`${API_BASE_URL}/resume/coherence`)
  if (targetRole) url.searchParams.append('target_role', targetRole)
  return fetch(url.toString(), { headers: authHeaders(token) }).then(handle)
}

export function getResumeTailoring(token, jobDescriptionId) {
  return fetch(`${API_BASE_URL}/resume/tailor/${jobDescriptionId}`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getResumeEvolution(token) {
  return fetch(`${API_BASE_URL}/resume/evolution`, {
    headers: authHeaders(token),
  }).then(handle)
}
