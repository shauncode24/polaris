import { Link } from 'react-router-dom'
import Button from '../common/Button'
import './PlanSummaryCard.css'

function buildWhyText(plan) {

  const job = plan.target_job
  if (job) {
    const parts = []
    parts.push(
      job.company ? `This roadmap targets the ${job.role || 'target'} role at ${job.company}.`
                  : `This roadmap targets the ${job.role || 'target'} role.`
    )
    if (job.missing_skills?.length > 0) {
      parts.push(
        `It prioritizes ${job.missing_skills.slice(0, 3).join(', ')} since your skill-gap analysis against this job flagged them as missing.`
      )
    }
    if (job.have_skills?.length > 0) {
      parts.push(`It builds on your verified strength in ${job.have_skills.slice(0, 3).join(', ')}.`)
    }
    if (job.overall_match_percentage != null) {
      parts.push(`Your current match against this job is ${Math.round(job.overall_match_percentage)}% (${job.overall_match_label}).`)
    }
    return parts.join(' ')
  }


  const weak = (plan.topic_signals || []).filter((t) => t.coverage === 'weak' || t.coverage === 'none')
  const strong = (plan.topic_signals || []).filter((t) => t.coverage === 'strong')

  const parts = []
  if (plan.relevant_domains?.length > 0) {
    parts.push(`This roadmap is scoped to ${plan.relevant_domains.join(', ').replace(/_/g, ' ')}.`)
  }
  if (weak.length > 0) {
    parts.push(
      `It prioritizes ${weak.slice(0, 3).map((t) => t.topic).join(', ')} since your profile currently shows little or no verified evidence there.`
    )
  }
  if (strong.length > 0) {
    parts.push(`It builds on your existing strength in ${strong.slice(0, 3).map((t) => t.topic).join(', ')}.`)
  }
  return parts.join(' ') || 'This roadmap was generated from your current profile and goal.'
}

function PlanSummaryCard({ goal, plan, onRegenerate, busy }) {
  return (
    <section className="plan-summary">
      {plan.degraded && (
        <p className="plan-summary__degraded-notice">
          Part of this plan used a simplified fallback for a few days — the rest was generated normally.
        </p>
      )}

      <div className="plan-summary__header">
        <h2>{goal.title}</h2>
        <div className="plan-summary__meta">
          {goal.deadline && <span>Target date: {goal.deadline}</span>}
          {goal.priority && <span>Priority: {goal.priority}</span>}
          <span>{plan.days_available}-day plan</span>
        </div>
      </div>

      {plan.relevant_domains?.length > 0 && (
        <ul className="plan-summary__domains">
          {plan.relevant_domains.map((d) => <li key={d}>{d.replace(/_/g, ' ')}</li>)}
        </ul>
      )}

      <p className="plan-summary__why">{buildWhyText(plan)}</p>

      <div className="plan-summary__actions">
        <Button variant="outline" onClick={onRegenerate} disabled={busy}>
          {busy ? 'Regenerating…' : 'Regenerate Plan'}
        </Button>
        <Button as={Link} to="/jobs" variant="outline">
          Analyze Another Job
        </Button>
        <Button variant="outline" disabled title="Interview practice UI is coming soon">
          Practice Interview
        </Button>
      </div>
    </section>
  )
}

export default PlanSummaryCard