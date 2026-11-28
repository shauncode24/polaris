import { API_BASE_URL, apiFetch } from './client'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    // A refused field comes as a list; the server's own message follows "Value error, ".
    const detail = Array.isArray(data.detail)
      ? data.detail[0]?.msg?.replace(/^Value error, /, '')
      : data.detail
    throw new Error((typeof detail === 'string' && detail) || 'Something went wrong.')
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// The newest version unless `version` is given.
export function getInterviewKit(token, jobId, version = null) {
  const query = version ? `?version=${version}` : ''
  return fetch(`${API_BASE_URL}/interview/kits/${jobId}${query}`, {
    headers: authHeaders(token),
  }).then(handle)
}

// Makes the next version. Runs as a background job, so it can take a while.
export function generateInterviewKit(token, jobId) {
  return apiFetch(`${API_BASE_URL}/interview/kits/${jobId}`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function matchKitEvidence(token, jobId, version) {
  return apiFetch(`${API_BASE_URL}/interview/kits/${jobId}/versions/${version}/evidence`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

// Newest first.
export function getPracticeAttempts(token, questionId) {
  return fetch(`${API_BASE_URL}/interview/questions/${questionId}/attempts`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function submitPracticeAnswer(token, questionId, answer) {
  return apiFetch(`${API_BASE_URL}/interview/questions/${questionId}/attempts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ answer }),
  }).then(handle)
}

export function getStudyPlan(token, jobId) {
  return fetch(`${API_BASE_URL}/interview/study-plan/${jobId}`, {
    headers: authHeaders(token),
  }).then(handle)
}
