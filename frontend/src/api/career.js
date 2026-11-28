// frontend/src/api/career.js
import { API_BASE_URL, apiFetch } from './client'
import { authFetch } from './session'

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

export function createGoal(token, { title, deadline, priority, jobIntelligenceId }) {
  return authFetch(`${API_BASE_URL}/goals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      title,
      deadline: deadline || null,
      priority: priority || null,
      job_intelligence_id: jobIntelligenceId || null,
    }),
  }).then(handle)
}

export function listGoals(token) {
  return authFetch(`${API_BASE_URL}/goals`, { headers: authHeaders(token) }).then(handle)
}

export function updateGoal(token, goalId, { title, deadline, priority } = {}) {
  return authFetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ title, deadline: deadline || null, priority: priority || null }),
  }).then(handle)
}

export function deleteGoal(token, goalId) {
  return authFetch(`${API_BASE_URL}/goals/${goalId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  }).then(handle)
}

export function generatePlan(token, goalId) {
  return apiFetch(`${API_BASE_URL}/goals/${goalId}/plan`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}