import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import FormField from './FormField'
import PasswordField from './PasswordField'
import AuthMessage from './AuthMessage'
import SocialAuthButtons from './SocialAuthButtons'
import Button from '../common/Button'
import './AuthForm.css'

function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login({ email, password })
      navigate('/home')
    } catch (err) {
      setError(err.message || 'Could not log in. Please check your credentials and try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h1 className="auth-form__title">Welcome back</h1>
      <p className="auth-form__subtitle">
        Don&apos;t have an account? <Link to="/signup">Sign up</Link>
      </p>

      <AuthMessage tone="error">{error}</AuthMessage>

      <FormField
        label="Email"
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
        autoComplete="email"
      />
      <PasswordField value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />

      <Button type="submit" variant="primary" size="md" className="auth-form__submit" disabled={submitting}>
        {submitting ? 'Logging in…' : 'Log in'}
      </Button>

      <SocialAuthButtons onError={setError} />
    </form>
  )
}

export default LoginForm