// frontend/src/api/resume.js
import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

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
  return authFetch(`${API_BASE_URL}/resume/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}

// Fetches the stored PDF with the auth header and returns it as a Blob, so
// the token is never placed in a URL.
export async function fetchResumePdf(token) {
  const response = await authFetch(`${API_BASE_URL}/resume/download`, {
    headers: authHeaders(token),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error((typeof data.detail === 'string' && data.detail) || 'Could not load the PDF.')
  }
  return response.blob()
}

export function uploadResume(file, token) {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch(`${API_BASE_URL}/resume/upload`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function runResumeReview(token) {
  return apiFetch(`${API_BASE_URL}/resume/review`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function runResumeAnalysis(token, jobIntelligenceId = null) {
  const url = new URL(`${API_BASE_URL}/resume/analyze`)
  if (jobIntelligenceId) {
    url.searchParams.append('job_intelligence_id', jobIntelligenceId)
  }
  return apiFetch(url.toString(), {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function getResumeCoherence(token, targetRole = null, regenerate = false) {
  const url = new URL(`${API_BASE_URL}/resume/coherence`)
  if (targetRole) url.searchParams.append('target_role', targetRole)
  if (regenerate) url.searchParams.append('regenerate', 'true')
  return apiFetch(url.toString(), { headers: authHeaders(token) }).then(handle)
}

export function getResumeEvolution(token) {
  return authFetch(`${API_BASE_URL}/resume/evolution`, {
    headers: authHeaders(token),
  }).then(handle)
}