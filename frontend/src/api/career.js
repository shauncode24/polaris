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

export function createGoal(token, { title, deadline, priority, jobDescriptionId }) {
  return fetch(`${API_BASE_URL}/goals`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      title,
      deadline: deadline || null,
      priority: priority || null,
      job_description_id: jobDescriptionId || null,
    }),
  }).then(handle)
}

export function listGoals(token) {
  return fetch(`${API_BASE_URL}/goals`, { headers: authHeaders(token) }).then(handle)
}

export function generatePlan(token, goalId) {
  return fetch(`${API_BASE_URL}/goals/${goalId}/plan`, {
    method: 'POST',
    headers: authHeaders(token),
  }).then(handle)
}