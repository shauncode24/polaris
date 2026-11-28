import { postAuth, startSession } from './session'

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
