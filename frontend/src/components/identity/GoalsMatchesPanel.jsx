// frontend/src/components/identity/GoalsMatchesPanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './GoalsMatchesPanel.css'

// Surfaces facts.active_goals and facts.recent_job_matches — both
// gathered by identity_builder.py but previously never shown anywhere
// on the Identity page.
function GoalsMatchesPanel({ goals = [], jobMatches = [] }) {
  if (goals.length === 0 && jobMatches.length === 0) return null

  return (
    <CollapsibleSection title="Active Goals & Recent Job Matches" defaultOpen={false}>
      <div className="goals-matches">
        {goals.length > 0 && (
          <div className="goals-matches__section">
            <span className="goals-matches__section-title">Active Goals</span>
            <ul className="goals-matches__list">
              {goals.map((g, i) => (
                <li key={i} className="goals-matches__goal">
                  <span className="goals-matches__goal-title">{g.title}</span>
                  <span className="goals-matches__goal-meta">
                    {g.priority ? `${g.priority} · ` : ''}{g.status_pct}% complete
                    {g.deadline ? ` · due ${g.deadline}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {jobMatches.length > 0 && (
          <div className="goals-matches__section">
            <span className="goals-matches__section-title">Recent Job Matches</span>
            <ul className="goals-matches__list">
              {jobMatches.map((m, i) => (
                <li key={i} className="goals-matches__match">
                  <span>{m.role || 'Unknown role'}{m.company ? ` at ${m.company}` : ''}</span>
                  {m.match_percentage != null && (
                    <span className="goals-matches__match-pct">
                      {Math.round(m.match_percentage)}% ({m.match_label})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default GoalsMatchesPanel