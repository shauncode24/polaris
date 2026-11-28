import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { confirmEmail } from '../api/auth'
import { renewSession } from '../api/session'
import AuthLayout from '../components/auth/AuthLayout'
import AuthMessage from '../components/auth/AuthMessage'
import Button from '../components/common/Button'
import '../components/auth/AuthForm.css'

// Confirms on a click, not on opening: mail scanners open links by themselves.
function ConfirmEmailPage() {
  const linkToken = new URLSearchParams(useLocation().hash.slice(1)).get('token')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleClick() {
    setError('')
    setSubmitting(true)
    try {
      await confirmEmail(linkToken)
      setDone(true)
      renewSession().catch(() => {}) // so a signed-in page here learns of it
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <div className="auth-form">
        <h1 className="auth-form__title">{done ? 'Email confirmed' : 'Confirm your email'}</h1>
        <AuthMessage tone="error">{error}</AuthMessage>

        {done ? (
          <p className="auth-form__subtitle">
            AI features are now available. <Link to="/home">Continue to Polaris</Link>
          </p>
        ) : !linkToken ? (
          <p className="auth-form__subtitle">This link is incomplete. Open the whole link from the email.</p>
        ) : (
          <>
            <p className="auth-form__subtitle">
              Only do this if you signed up for Polaris yourself.
            </p>
            <Button variant="primary" size="md" className="auth-form__submit" onClick={handleClick} disabled={submitting}>
              {submitting ? 'Confirming…' : 'Confirm my email address'}
            </Button>
            {error && (
              <p className="auth-form__subtitle">
                <Link to="/home">Sign in</Link> to have a new link sent.
              </p>
            )}
          </>
        )}
      </div>
    </AuthLayout>
  )
}

export default ConfirmEmailPage
