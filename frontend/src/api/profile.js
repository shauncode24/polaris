import { API_BASE_URL, apiFetch } from './client'

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

export function uploadResume(file, token) {
  const formData = new FormData()
  formData.append('file', file)
  return apiFetch(`${API_BASE_URL}/resume/upload`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function syncGithub(token, { username, githubToken } = {}) {
  return apiFetch(`${API_BASE_URL}/sync/github`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ username: username || null, token: githubToken || null }),
  }).then(handle)
}

export function syncLeetcode(token, { username } = {}) {
  return fetch(`${API_BASE_URL}/sync/leetcode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ username: username || null }),
  }).then(handle)
}

export function submitLeetcodeManual(token, tagCounts) {
  return fetch(`${API_BASE_URL}/sync/leetcode/manual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ tag_counts: tagCounts }),
  }).then(handle)
}

export function getProfileData(token) {
  return fetch(`${API_BASE_URL}/profile/data`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getLeetcodeWorkspace(token) {
  return fetch(`${API_BASE_URL}/sync/leetcode/workspace`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function runLeetcodePortfolioReview(token) {
  return apiFetch(`${API_BASE_URL}/sync/leetcode/review`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

// Confirm, edit, hide or restore one project / experience / education entry.
// kind: 'projects' | 'experiences' | 'education'; action: 'confirm' | 'edit' | 'hide' | 'unhide'.
export function reviewEvidenceItem(token, kind, itemId, action, fields = null) {
  return fetch(`${API_BASE_URL}/profile/${kind}/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ action, fields }),
  }).then(handle)
}

export function setSkillVisibility(token, skill, hidden) {
  return fetch(`${API_BASE_URL}/profile/skills/${encodeURIComponent(skill)}/visibility`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ hidden }),
  }).then(handle)
}
