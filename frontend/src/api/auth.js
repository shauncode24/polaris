import { API_BASE_URL } from './config'
import { authFetch, postAuth, startSession } from './session'

// A refused field arrives as a list of problems; other errors as plain text.
function errorMessage(detail) {
  if (Array.isArray(detail)) return detail[0]?.msg?.replace(/^Value error, /, '')
  return typeof detail === 'string' ? detail : undefined
}

async function handle(response) {
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(errorMessage(data.detail) || 'Something went wrong. Please try again.')
  }
  return data
}

function signIn(path, body) {
  return startSession(() => postAuth(path, body).then(handle))
}

export function register({ firstName, lastName, email, password }) {
  return signIn('register', { first_name: firstName, last_name: lastName, email, password })
}

export function login({ email, password }) {
  return signIn('login', { email, password })
}

export function googleAuth(credential) {
  return signIn('google', { credential })
}

export function forgotPassword(email) {
  return postAuth('password/forgot', { email }).then(handle)
}

// `linkToken` comes from the emailed link, here and below.
export function resetPassword(linkToken, password) {
  return postAuth('password/reset', { token: linkToken, password }).then(handle)
}

export function confirmEmail(linkToken) {
  return postAuth('email/confirm', { token: linkToken }).then(handle)
}

export function resendConfirmation(token) {
  return authFetch(`${API_BASE_URL}/auth/email/resend`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  }).then(handle)
}
