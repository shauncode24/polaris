import { useEffect, useState } from 'react'
import { getPracticeAttempts, submitPracticeAnswer } from '../../../api/interviewKit'
import AttemptFeedback from './AttemptFeedback'
import { percent } from './labels'

// The server's limits on an answer.
const MIN_LENGTH = 20
const MAX_LENGTH = 5000

export default function PracticePanel({ token, questionId, onPractised }) {
  const [answer, setAnswer] = useState('')
  const [attempts, setAttempts] = useState(null) // newest first; null until loaded
  const [openId, setOpenId] = useState(null)
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    getPracticeAttempts(token, questionId)
      .then((items) => {
        if (cancelled) return
        // An answer submitted while this was loading is already listed.
        setAttempts((current) => current ?? items)
        setOpenId((current) => current ?? items[0]?.id ?? null)
      })
      .catch((err) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [token, questionId])

  async function submit(event) {
    event.preventDefault()
    setSending(true)
    setError('')
    try {
      const attempt = await submitPracticeAnswer(token, questionId, answer.trim())
      setAttempts((current) => [attempt, ...(current ?? []).filter((a) => a.id !== attempt.id)])
      setOpenId(attempt.id)
      onPractised()
    } catch (err) {
      setError(err.message)
    } finally {
      setSending(false)
    }
  }

  const open = attempts?.find((attempt) => attempt.id === openId)
  const length = answer.trim().length

  return (
    <div className="ik-practice">
      <form onSubmit={submit}>
        <label className="ik-label" htmlFor={`answer-${questionId}`}>Your answer</label>
        <textarea
          id={`answer-${questionId}`}
          rows={6}
          maxLength={MAX_LENGTH}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="Answer as you would say it in the interview."
        />
        <div className="ik-actions">
          <button type="submit" className="ik-btn ik-btn--primary" disabled={sending || length < MIN_LENGTH}>
            {sending ? 'Reviewing…' : 'Get feedback'}
          </button>
          <span className="ik-hint">
            {length < MIN_LENGTH ? `At least ${MIN_LENGTH} characters.` : `${length} of ${MAX_LENGTH} characters.`}
          </span>
        </div>
      </form>

      {error && <p className="ik-banner ik-banner--error" role="alert">{error}</p>}

      {attempts?.length > 1 && (
        <label className="ik-history">
          <span className="ik-label">Attempt</span>
          <select value={openId ?? ''} onChange={(event) => setOpenId(event.target.value)}>
            {attempts.map((attempt, index) => (
              <option key={attempt.id} value={attempt.id}>
                {attempts.length - index}: {new Date(attempt.created_at).toLocaleString()}
                {attempt.score === null ? '' : `, ${percent(attempt.score)}`}
              </option>
            ))}
          </select>
        </label>
      )}

      <div aria-live="polite">
        {open && (
          <>
            <details className="ik-answered">
              <summary>The answer reviewed</summary>
              <p>{open.answer}</p>
            </details>
            <AttemptFeedback attempt={open} />
          </>
        )}
      </div>
    </div>
  )
}
