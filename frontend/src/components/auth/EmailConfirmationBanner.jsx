import { useEffect, useState } from 'react'
import { resendConfirmation } from '../../api/auth'
import { useAuth } from '../../contexts/AuthContext'
import './EmailConfirmationBanner.css'

// Shown on every signed-in page while AI features wait for a confirmed address.
function EmailConfirmationBanner() {
  const { token, user, refreshUser } = useAuth()
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [hidden, setHidden] = useState(false)
  const waiting = Boolean(user?.needs_email_confirmation)

  // The link is usually opened elsewhere: look again on coming back.
  useEffect(() => {
    if (!waiting) return undefined
    const check = () => refreshUser().catch(() => {})
    window.addEventListener('focus', check)
    return () => window.removeEventListener('focus', check)
  }, [waiting, refreshUser])

  if (!waiting || hidden) return null

  async function run(action) {
    setBusy(true)
    setMessage('')
    try {
      await action()
    } catch (err) {
      setMessage(err.message)
    } finally {
      setBusy(false)
    }
  }

  const resend = () => run(async () => {
    const { detail } = await resendConfirmation(token)
    setMessage(detail)
    await refreshUser() // it may have been confirmed already
  })

  const checkAgain = () => run(async () => {
    const session = await refreshUser()
    if (session?.user.needs_email_confirmation) {
      setMessage("It isn't confirmed yet. Open the link in the email.")
    }
  })

  return (
    <aside className="email-banner" aria-label="Email confirmation">
      <p className="email-banner__text">
        <strong>Confirm your email to use AI features.</strong>{' '}
        We sent a link to {user.email}.
      </p>
      <p className="email-banner__message" role="status">{message}</p>
      <div className="email-banner__actions">
        <button type="button" onClick={resend} disabled={busy}>Send it again</button>
        <button type="button" onClick={checkAgain} disabled={busy}>I&apos;ve confirmed it</button>
        <button type="button" onClick={() => setHidden(true)}>Hide</button>
      </div>
    </aside>
  )
}

export default EmailConfirmationBanner
