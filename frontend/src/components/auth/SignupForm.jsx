import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import FormField from './FormField'
import PasswordField from './PasswordField'
import CheckboxField from './CheckboxField'
import AuthMessage from './AuthMessage'
import SocialAuthButtons from './SocialAuthButtons'
import Button from '../common/Button'
import './AuthForm.css'

function SignupForm() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [agreed, setAgreed] = useState(false)
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!agreed) {
      setError('Please agree to the Terms & Conditions to continue.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters long.')
      return
    }

    setSubmitting(true)
    try {
      await register({ firstName, lastName, email, password })
      navigate('/home')
    } catch (err) {
      setError(err.message || 'Could not create your account. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h1 className="auth-form__title">Create an account</h1>
      <p className="auth-form__subtitle">
        Already have an account? <Link to="/login">Log in</Link>
      </p>

      <AuthMessage tone="error">{error}</AuthMessage>

      <div className="auth-form__row">
        <FormField placeholder="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required autoComplete="given-name" />
        <FormField placeholder="Last name" value={lastName} onChange={(e) => setLastName(e.target.value)} autoComplete="family-name" />
      </div>

      <FormField type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
      <PasswordField value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" />

      <CheckboxField checked={agreed} onChange={(e) => setAgreed(e.target.checked)}>
        I agree to the <Link to="/terms">Terms &amp; Conditions</Link>
      </CheckboxField>

      <Button type="submit" variant="primary" size="md" className="auth-form__submit" disabled={submitting}>
        {submitting ? 'Creating account…' : 'Create account'}
      </Button>

      <SocialAuthButtons onError={setError} />
    </form>
  )
}

export default SignupForm