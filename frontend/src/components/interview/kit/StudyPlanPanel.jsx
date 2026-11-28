import { useEffect, useState } from 'react'
import { getStudyPlan } from '../../../api/interviewKit'
import { CATEGORY_LABELS, percent } from './labels'

function Questions({ title, questions }) {
  if (questions.length === 0) return null
  return (
    <div>
      <p className="ik-label">{title}</p>
      <ul className="ik-list">
        {questions.map((q) => (
          <li key={q.question_id}>
            {q.text}
            {q.latest_score !== null && <span className="ik-hint"> ({percent(q.latest_score)})</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Gap({ gap }) {
  return (
    <li className="ik-card">
      <div className="ik-chips">
        <h3>{gap.name}</h3>
        <span className={`ik-chip ik-chip--${gap.severity}`}>{gap.severity}</span>
      </div>
      <p>{gap.why} {gap.action}</p>
      {gap.leetcode.length > 0 && (
        <ul className="ik-chips" aria-label={`LeetCode topics for ${gap.name}`}>
          {gap.leetcode.map((topic) => (
            <li key={topic.topic}>
              <a className="ik-chip ik-chip--link" href={topic.url} target="_blank" rel="noopener noreferrer">
                {topic.topic}{topic.solved === null ? '' : `: ${topic.solved} solved`}
              </a>
            </li>
          ))}
        </ul>
      )}
      <Questions title="Interview questions about it" questions={gap.questions} />
    </li>
  )
}

// Worked out afresh each time it is shown; `revision` changes when practice or
// the kit does.
export default function StudyPlanPanel({ token, jobId, revision }) {
  const [loaded, setLoaded] = useState(null) // { jobId, plan }
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    setError('')
    getStudyPlan(token, jobId)
      .then((plan) => { if (!cancelled) setLoaded({ jobId, plan }) })
      .catch((err) => { if (!cancelled) setError(err.message) })
    return () => { cancelled = true }
  }, [token, jobId, revision])

  if (error) return <p className="ik-banner ik-banner--error" role="alert">{error}</p>
  // Nothing from another job stays on screen while this one loads.
  if (loaded?.jobId !== jobId) return <p className="ik-hint">Working out your study plan…</p>
  const { plan } = loaded

  return (
    <div className="ik-study">
      {plan.notes.map((note) => <p key={note} className="ik-hint">{note}</p>)}
      {plan.kit_version !== null && (
        <p className="ik-hint">Questions are from version {plan.kit_version}, the newest kit.</p>
      )}
      {plan.weakest_category && <p>Weakest area so far: <strong>{CATEGORY_LABELS[plan.weakest_category]}</strong></p>}

      {plan.gaps.length === 0 ? (
        <div className="ik-card"><p>Your record shows every skill this job names.</p></div>
      ) : (
        <ul className="ik-study__gaps">
          {plan.gaps.map((gap) => <Gap key={gap.skill} gap={gap} />)}
        </ul>
      )}

      {(plan.unanswered.length > 0 || plan.weak.length > 0) && (
        <div className="ik-card">
          <Questions title="Questions you have no example for yet" questions={plan.unanswered} />
          <Questions title="Worth practising again" questions={plan.weak} />
        </div>
      )}
    </div>
  )
}
