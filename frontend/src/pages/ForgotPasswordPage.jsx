import { useState } from 'react'
import { Link } from 'react-router-dom'
import { forgotPassword } from '../api/auth'
import AuthLayout from '../components/auth/AuthLayout'
import AuthMessage from '../components/auth/AuthMessage'
import FormField from '../components/auth/FormField'
import Button from '../components/common/Button'
import '../components/auth/AuthForm.css'

function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [sent, setSent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSent('')
    setSubmitting(true)
    try {
      const { detail } = await forgotPassword(email)
      setSent(detail)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout>
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1 className="auth-form__title">Forgot your password?</h1>
        <p className="auth-form__subtitle">
          Enter your email address and we&apos;ll send you a link to set a new one.
        </p>

        <AuthMessage tone="error">{error}</AuthMessage>
        <AuthMessage tone="success">{sent}</AuthMessage>

        <FormField
          label="Email"
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
        />

        <Button type="submit" variant="primary" size="md" className="auth-form__submit" disabled={submitting}>
          {submitting ? 'Sending…' : 'Send the link'}
        </Button>

        <p className="auth-form__subtitle">
          <Link to="/login">Back to log in</Link>
        </p>
      </form>
    </AuthLayout>
  )
}

export default ForgotPasswordPage
