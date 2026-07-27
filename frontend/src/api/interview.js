// frontend/src/api/interview.js
import { API_BASE_URL } from './client'

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(
      (typeof data.detail === 'string' && data.detail) || data.reason || 'Something went wrong.'
    )
  }
  return data
}

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function askInterviewQuestion(token, { question, targetRole, targetCompany }) {
  return fetch(`${API_BASE_URL}/interview/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      question,
      target_role: targetRole || null,
      target_company: targetCompany || null,
    }),
  }).then(handle)
}

export function listInterviewSessions(token) {
  return fetch(`${API_BASE_URL}/interview/sessions`, {
    headers: authHeaders(token),
  }).then(handle)
}