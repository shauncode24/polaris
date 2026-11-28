import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

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
  return authFetch(`${API_BASE_URL}/tailored-resumes/${jobId}${query}`, {
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
  return authFetch(`${API_BASE_URL}/tailored-resumes/${jobId}/versions/${version}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify(changes),
  }).then(handle)
}

// Saves the version as a file ('pdf' or 'docx') through the browser's download.
// Fetched with the header, so the token is never placed in a URL.
export async function downloadTailoredResume(token, jobId, version, format) {
  const response = await authFetch(
    `${API_BASE_URL}/tailored-resumes/${jobId}/versions/${version}/export?format=${format}`,
    { headers: authHeaders(token) },
  )
  if (!response.ok) await handle(response) // throws with the server's message

  const named = /filename\*=UTF-8''([^;]+)/.exec(response.headers.get('Content-Disposition') ?? '')
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = named ? decodeURIComponent(named[1]) : `resume.${format}`
  document.body.append(link)
  link.click()
  link.remove()
  // Released later: some browsers start reading the file after the click returns.
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
