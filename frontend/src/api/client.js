import { API_BASE_URL } from './config'
import { authFetch } from './session'

// Slow requests (mostly AI work) are answered with 202 and a job id; the job is
// then checked until it has finished.
const POLL_DELAYS_MS = [700, 1000, 1500, 2000, 3000]
// Checks in a row that may fail (server restarting, network blip) before giving up.
const MAX_FAILED_CHECKS = 10

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

async function waitForJob(jobId, headers) {
  let failedChecks = 0
  for (let check = 0; ; check += 1) {
    const delay = POLL_DELAYS_MS[Math.min(check, POLL_DELAYS_MS.length - 1)]
    await new Promise((resolve) => setTimeout(resolve, delay))

    let response
    try {
      response = await authFetch(`${API_BASE_URL}/background-jobs/${jobId}`, { headers })
    } catch (error) {
      failedChecks += 1
      if (failedChecks >= MAX_FAILED_CHECKS) throw error
      continue
    }
    if (response.status === 429) continue // rate limited: keep waiting
    if (response.status >= 500 && ++failedChecks < MAX_FAILED_CHECKS) continue
    if (!response.ok) return response

    failedChecks = 0
    const job = await response.json()
    if (job.status === 'succeeded') return jsonResponse(200, job.result)
    if (job.status === 'failed') return jsonResponse(job.error_status || 500, { detail: job.error_detail })
  }
}

// `authFetch` for requests that may run as a background job. The promise resolves
// when the work is done, with the response the request would have given.
export async function apiFetch(url, options = {}) {
  const response = await authFetch(url, options)
  if (response.status !== 202) return response
  const { job_id: jobId } = await response.json()
  const authorization = options.headers?.Authorization
  return waitForJob(jobId, authorization ? { Authorization: authorization } : {})
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`)
  }

  return response.json()
}

export function checkHealth() {
  return request('/health')
}

export { API_BASE_URL }
