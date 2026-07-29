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

export function listProjects(token) {
  return fetch(`${API_BASE_URL}/projects`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getProjectsInsights(token) {
  return fetch(`${API_BASE_URL}/projects/insights`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getLinkSuggestions(token) {
  return fetch(`${API_BASE_URL}/projects/link-suggestions`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function confirmProjectLink(token, projectId, repoName) {
  return fetch(`${API_BASE_URL}/projects/${projectId}/link`, {
    method: 'POST',
    headers: {
      ...authHeaders(token),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ repo_name: repoName }),
  }).then(handle)
}

export function removeProjectLink(token, projectId) {
  return fetch(`${API_BASE_URL}/projects/${projectId}/link`, {
    method: 'DELETE',
    headers: authHeaders(token),
  }).then(handle)
}

export function explainProject(token, projectId, framing = 'general') {
  return fetch(`${API_BASE_URL}/projects/${projectId}/intelligence/explain?framing=${encodeURIComponent(framing)}`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function compareProject(token, projectId, comparisonTarget) {
  return fetch(`${API_BASE_URL}/projects/${projectId}/intelligence/compare?comparison_target=${encodeURIComponent(comparisonTarget)}`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}