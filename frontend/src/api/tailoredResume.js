import { API_BASE_URL, apiFetch } from './client'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error((typeof data.detail === 'string' && data.detail) || 'Something went wrong.')
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// The newest version unless `version` is given.
export function getTailoredResume(token, jobId, version = null) {
  const query = version ? `?version=${version}` : ''
  return fetch(`${API_BASE_URL}/tailored-resumes/${jobId}${query}`, {
    headers: authHeaders(token),
  }).then(handle)
}

// Makes the next version. Runs as a background job, so it can take a while.
export function generateTailoredResume(token, jobId) {
  return apiFetch(`${API_BASE_URL}/tailored-resumes/${jobId}`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

// `changes` is { lines: [{ line_id, decision, edited, confirm_flags }], section_order }.
export function changeTailoredResume(token, jobId, version, changes) {
  return fetch(`${API_BASE_URL}/tailored-resumes/${jobId}/versions/${version}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(changes),
  }).then(handle)
}
