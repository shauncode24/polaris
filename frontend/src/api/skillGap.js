import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      (typeof data.detail === 'string' && data.detail) ||
        data.reason ||
        'Something went wrong loading this skill gap analysis.'
    )
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Job selection reads from the Job Intelligence module directly — Skill
// Gap never re-parses a JD, it only ever picks from what's already there.
export function listParsedJobs(token) {
  return authFetch(`${API_BASE_URL}/job-intelligence`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}

export function getSkillGapForJob(token, jobIntelligenceId, { regenerate = false } = {}) {
  const qs = regenerate ? '?regenerate=true' : ''
  return apiFetch(`${API_BASE_URL}/jobs/by-intelligence/${jobIntelligenceId}${qs}`, {
    headers: { ...authHeaders(token) },
  }).then(handle)
}