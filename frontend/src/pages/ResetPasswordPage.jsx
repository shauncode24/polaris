import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { resetPassword } from '../api/auth'
import { signOutIfEnded } from '../api/session'
import AuthLayout from '../components/auth/AuthLayout'
import AuthMessage from '../components/auth/AuthMessage'
import PasswordField from '../components/auth/PasswordField'
import Button from '../components/common/Button'
import '../components/auth/AuthForm.css'

function ResetPasswordPage() {
  // After the `#`, so that it is never sent to a server.
  const linkToken = new URLSearchParams(useLocation().hash.slice(1)).get('token')
  const [password, setPassword] = useState('')
  const [repeated, setRepeated] = useState('')
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }
    if (password !== repeated) {
      setError("The two passwords don't match.")
      return
    }
    setSubmitting(true)
    try {
      await resetPassword(linkToken, password)
      setDone(true)
      // Signs this browser out if it was signed in to that account.
      signOutIfEnded().catch(() => {})
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (done || !linkToken) {
    return (
      <AuthLayout>
        <div className="auth-form">
          <h1 className="auth-form__title">{done ? 'Password changed' : 'This link is incomplete'}</h1>
          <p className="auth-form__subtitle">
            {done ? (
              <>You&apos;ve been signed out everywhere. <Link to="/login">Log in with your new password</Link></>
            ) : (
              <>Open the whole link from the email, or <Link to="/forgot-password">ask for a new one</Link></>
            )}
          </p>
        </div>
      </AuthLayout>
    )
  }

  return (
    <AuthLayout>
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1 className="auth-form__title">Choose a new password</h1>
        <p className="auth-form__subtitle">
          Link not working? <Link to="/forgot-password">Ask for a new one</Link>
        </p>

        <AuthMessage tone="error">{error}</AuthMessage>

        <PasswordField label="New password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <PasswordField
          label="Repeat it"
          placeholder="Enter it again"
          value={repeated}
          onChange={(e) => setRepeated(e.target.value)}
          required
        />

        <Button type="submit" variant="primary" size="md" className="auth-form__submit" disabled={submitting}>
          {submitting ? 'Saving…' : 'Set password'}
        </Button>
      </form>
    </AuthLayout>
  )
}

export default ResetPasswordPage
