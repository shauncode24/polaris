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

export function getGoalAwareRanking(token) {
  return fetch(`${API_BASE_URL}/projects/ranking`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getPortfolioNarrative(token, regenerate = false) {
  const url = new URL(`${API_BASE_URL}/projects/portfolio-narrative`)
  if (regenerate) url.searchParams.append('regenerate', 'true')
  return fetch(url.toString(), { headers: authHeaders(token) }).then(handle)
}

export function getProjectClaimAudit(token, projectId, regenerate = false) {
  const url = new URL(`${API_BASE_URL}/projects/${projectId}/claim-audit`)
  if (regenerate) url.searchParams.append('regenerate', 'true')
  return fetch(url.toString(), { headers: authHeaders(token) }).then(handle)
}

export function getProjectIntelligence(token, projectId, { framing, comparisonTarget, regenerate = false } = {}) {
  const url = new URL(`${API_BASE_URL}/projects/${projectId}/intelligence`)
  if (framing) url.searchParams.append('framing', framing)
  if (comparisonTarget) url.searchParams.append('comparison_target', comparisonTarget)
  if (regenerate) url.searchParams.append('regenerate', 'true')
  return fetch(url.toString(), { headers: authHeaders(token) }).then(handle)
}

export function getProjectInterviewQuestions(token, projectId, regenerate = false) {
  const url = new URL(`${API_BASE_URL}/projects/${projectId}/interview-questions`)
  if (regenerate) url.searchParams.append('regenerate', 'true')
  return fetch(url.toString(), { headers: authHeaders(token) }).then(handle)
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

export function unlinkProject(token, projectId) {
  return fetch(`${API_BASE_URL}/projects/${projectId}/unlink`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}

export function getLinkOptions(token) {
  return fetch(`${API_BASE_URL}/projects/link-options`, {
    headers: authHeaders(token),
  }).then(handle)
}