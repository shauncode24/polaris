// frontend/src/api/companyNotes.js
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

export function listCompanyNotes(token, company) {
  const query = company ? `?company=${encodeURIComponent(company)}` : ''
  return fetch(`${API_BASE_URL}/company-notes${query}`, { headers: authHeaders(token) }).then(handle)
}

export function createCompanyNote(token, { company, content }) {
  return fetch(`${API_BASE_URL}/company-notes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders(token) },
    body: JSON.stringify({ company, pasted_content: content }),
  }).then(handle)
}