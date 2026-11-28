// frontend/src/api/jobIntelligence.js
import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      (typeof data.detail === 'string' && data.detail) ||
        data.reason ||
        'Something went wrong analyzing this job.'
    )
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function analyzeJobIntelligenceText(token, { rawText, company, role }) {
  return apiFetch(`${API_BASE_URL}/job-intelligence/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      raw_text: rawText,
      company: company || null,
      role: role || null,
    }),
  }).then(handle)
}

export function analyzeJobIntelligencePdf(token, file, { company, role } = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (company) formData.append('company', company)
  if (role) formData.append('role', role)

  return apiFetch(`${API_BASE_URL}/job-intelligence/analyze-pdf`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function listJobIntelligenceProfiles(token) {
  return authFetch(`${API_BASE_URL}/job-intelligence`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}

export function setPrimaryJob(token, jobIntelligenceId, primary) {
  return authFetch(`${API_BASE_URL}/job-intelligence/${jobIntelligenceId}/primary`, {
    method: primary ? 'PUT' : 'DELETE',
    headers: authHeaders(token),
  }).then(handle)
}

export function deleteJob(token, jobIntelligenceId) {
  return authFetch(`${API_BASE_URL}/job-intelligence/${jobIntelligenceId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  }).then(handle)
}

export function compareJobs(token, jobIntelligenceIds) {
  const query = new URLSearchParams(jobIntelligenceIds.map((id) => ['ids', id]))
  return authFetch(`${API_BASE_URL}/job-intelligence/compare?${query}`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getJobIntelligenceProfile(token, jobIntelligenceId) {
  return authFetch(`${API_BASE_URL}/job-intelligence/${jobIntelligenceId}`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}