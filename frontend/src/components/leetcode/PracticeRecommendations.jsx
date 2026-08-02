// frontend/src/components/leetcode/PracticeRecommendations.jsx
// Renders insights.recommendations — deterministic, rule-based action
// items from leetcode_insights.build_recommendations() (priority +
// reason + action). Distinct from the LLM Coach's target_focus_topics/
// roadmap_actions: this is a separate, always-available signal that
// was previously computed by the backend but never surfaced anywhere
// in the frontend.
import './PracticeRecommendations.css'

const PRIORITY_ORDER = { High: 0, Medium: 1, Low: 2 }

function PracticeRecommendations({ recommendations }) {
  if (!recommendations || recommendations.length === 0) return null

  const sorted = [...recommendations].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 3) - (PRIORITY_ORDER[b.priority] ?? 3)
  )

  return (
    <section className="lc-card">
      <h3>Practice recommendations</h3>
      <p className="lc-card__lead">Rule-based next actions, computed directly from your solved-problem history.</p>
      <ul className="pr-list">
        {sorted.map((r, i) => (
          <li key={i} className={`pr-item pr-item--${(r.priority || 'low').toLowerCase()}`}>
            <span className={`pr-item__badge pr-item__badge--${(r.priority || 'low').toLowerCase()}`}>
              {r.priority}
            </span>
            <div className="pr-item__body">
              <span className="pr-item__action">{r.action}</span>
              <span className="pr-item__reason">{r.reason}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default PracticeRecommendations