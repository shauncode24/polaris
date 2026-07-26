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

export function uploadResume(file, token) {
  const formData = new FormData()
  formData.append('file', file)
  return fetch(`${API_BASE_URL}/resume/upload`, {
    method: 'POST',
    headers: authHeaders(token),
    body: formData,
  }).then(handle)
}

export function syncGithub(token, { username, githubToken } = {}) {
  return fetch(`${API_BASE_URL}/sync/github`, {
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