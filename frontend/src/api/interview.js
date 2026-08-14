// frontend/src/api/interview.js
import { API_BASE_URL } from './client'

/**
 * Parses backend responses, handling both:
 *   - Normal API errors: detail is a string or {msg} object (FastAPI validation)
 *   - Structured 502 degraded errors: detail is {error_type, message, trace_id}
 *     (implementation plan §S — three distinct failure classes must be distinguishable)
 *
 * On error, throws an object (not a bare Error string) so callers can inspect
 * error_type and trace_id without string-parsing:
 *   { message, error_type, trace_id }
 */
async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    // Structured degraded-service error (§S)
    if (detail && typeof detail === 'object' && detail.error_type) {
      const err = new Error(detail.message || 'Generation service temporarily unavailable.')
      err.error_type = detail.error_type
      err.trace_id = detail.trace_id || null
      throw err
    }
    // Standard FastAPI error (string detail or validation array)
    const msg =
      (typeof detail === 'string' && detail) ||
      (Array.isArray(detail) && detail[0]?.msg) ||
      data.reason ||
      'Something went wrong.'
    throw new Error(msg)
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