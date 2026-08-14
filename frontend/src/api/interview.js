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

export function askInterviewQuestion(
  token,
  { question, targetRole, targetCompany, jobIntelligenceId, sessionId, parentResponseId, correction }
) {
  return fetch(`${API_BASE_URL}/interview/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      question,
      target_role: targetRole || null,
      target_company: targetCompany || null,
      job_intelligence_id: jobIntelligenceId || null,
      session_id: sessionId || null,
      parent_response_id: parentResponseId || null,
      correction: correction || null,
    }),
  }).then(handle)
}

export function correctInterviewResponse(token, { parentResponseId, correction }) {
  return fetch(`${API_BASE_URL}/interview/correct`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({
      parent_response_id: parentResponseId,
      correction,
    }),
  }).then(handle)
}

export function listInterviewSessions(token) {
  return fetch(`${API_BASE_URL}/interview/sessions`, {
    headers: authHeaders(token),
  }).then(handle)
}

export function getInterviewSessionThread(token, sessionId) {
  return fetch(`${API_BASE_URL}/interview/sessions/${sessionId}`, {
    headers: authHeaders(token),
  }).then(handle)
}