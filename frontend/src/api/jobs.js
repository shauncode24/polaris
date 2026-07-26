import { API_BASE_URL } from './client'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      (typeof data.detail === 'string' && data.detail) ||
        data.reason ||
        'Something went wrong analyzing this job description.'
    )
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function analyzeJobText(token, { rawText, company, role }) {
  return fetch(`${API_BASE_URL}/jobs/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      raw_text: rawText,
      company: company || null,
      role: role || null,
    }),
  }).then(handle)
}

export function analyzeJobPdf(token, file, { company, role } = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (company) formData.append('company', company)
  if (role) formData.append('role', role)

  return fetch(`${API_BASE_URL}/jobs/analyze-pdf`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function listJobAnalyses(token) {
  return fetch(`${API_BASE_URL}/jobs`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}

export function getJobAnalysis(token, jobId) {
  return fetch(`${API_BASE_URL}/jobs/${jobId}`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}