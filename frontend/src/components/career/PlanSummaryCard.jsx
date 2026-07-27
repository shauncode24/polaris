// frontend/src/components/career/PlanSummaryCard.jsx
import Button from '../common/Button'
import './PlanSummaryCard.css'

function deriveTags(plan) {
  if (plan.target_job) {
    const tags = []
    if (plan.target_job.role) tags.push(plan.target_job.role.toLowerCase())
    return [...tags, ...(plan.target_job.missing_skills || []).slice(0, 2).map((s) => s.replace(/_/g, ' '))]
  }
  return (plan.relevant_domains || []).map((d) => d.replace(/_/g, ' '))
}

function buildDescription(plan) {
  const job = plan.target_job
  if (job) {
    const parts = []
    if (job.missing_skills?.length > 0) {
      parts.push(
        `This plan focuses on the missing skills from your ${job.company ? `${job.company} ` : ''}analysis — ${job.missing_skills.slice(0, 2).join(' and ')} — before deepening what you already have.`
      )
    }
    if (job.have_skills?.length > 0) {
      parts.push(`Your evidenced ${job.have_skills.slice(0, 2).join(', ')} strengths stay in the loop through practice, not more study.`)
    }
    return parts.join(' ') || 'This roadmap was generated from your current profile and goal.'
  }

  const weak = (plan.topic_signals || []).filter((t) => t.coverage === 'weak' || t.coverage === 'none')
  const strong = (plan.topic_signals || []).filter((t) => t.coverage === 'strong')
  const parts = []
  if (weak.length > 0) parts.push(`It prioritizes ${weak.slice(0, 3).map((t) => t.topic).join(', ')} since your profile shows little verified evidence there.`)
  if (strong.length > 0) parts.push(`It builds on your existing strength in ${strong.slice(0, 3).map((t) => t.topic).join(', ')}.`)
  return parts.join(' ') || 'This roadmap was generated from your current profile and goal.'
}

function PlanSummaryCard({ goal, plan, onRegenerate, busy }) {
  const tags = deriveTags(plan)

  return (
    <section className="plan-summary">
      {plan.degraded && (
        <p className="plan-summary__degraded-notice">
          Part of this plan used a simplified fallback for a few days — the rest was generated normally.
        </p>
      )}

      <div className="plan-summary__top">
        <div className="plan-summary__title-row">
          <h2>{goal.title}</h2>
          {goal.priority && <span className={`plan-summary__priority plan-summary__priority--${goal.priority.toLowerCase()}`}>{goal.priority}</span>}
        </div>
        <div className="plan-summary__meta">
          {goal.deadline && (
            <span><CalendarDot />{plan.days_available} days available</span>
          )}
        </div>
      </div>

      {tags.length > 0 && (
        <ul className="plan-summary__tags">
          {tags.map((t) => <li key={t}>{t}</li>)}
        </ul>
      )}

      <p className="plan-summary__desc">{buildDescription(plan)}</p>

      <div className="plan-summary__actions">
        <Button variant="outline" onClick={onRegenerate} disabled={busy}>
          {busy ? 'Regenerating…' : '↻ Regenerate plan'}
        </Button>
        <a className="plan-summary__link" href="/jobs">Analyze another job →</a>
        <span className="plan-summary__soon" title="Coming soon">Practice interview · Soon</span>
      </div>
    </section>
  )
}

function CalendarDot() {
  return <span className="plan-summary__dot" />
}

export default PlanSummaryCard