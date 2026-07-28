import CollapsibleSection from '../common/CollapsibleSection'
import './PortfolioReviewPanel.css'

function RoleFitRow({ item }) {
  return (
    <div className="pr-role-row">
      <span className="pr-role-name">{item.role}</span>
      <span className="pr-role-stars">
        {'★'.repeat(item.rating)}{'☆'.repeat(Math.max(0, 5 - item.rating))}
      </span>
      <p className="pr-role-rationale">{item.rationale}</p>
    </div>
  )
}

function PortfolioReviewPanel({ review, onRun, loading }) {
  if (!review) {
    return (
      <div className="pr-panel">
        <div className="pr-panel__empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--border)' }}>
            <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
          </svg>
          <p>No AI portfolio review yet.</p>
          <button className="pr-panel__cta" onClick={onRun} disabled={loading}>
            {loading ? 'Reviewing…' : 'Run AI Portfolio Review'}
          </button>
        </div>
      </div>
    )
  }

  const {
    engineering_assessment, flagship_projects = [], role_fit = [],
    skill_confidence_explanations = [], engineering_habits = [],
    recruiter_perspective, resume_integration_suggestions = [],
    growth_story, improvement_roadmap = [], analysis_degraded,
  } = review

  return (
    <div className="pr-container">
      <div className="pr-header">
        <h3>AI Portfolio Review</h3>
        <button className="pr-refresh" onClick={onRun} disabled={loading}>
          {loading ? 'Reviewing…' : '↻ Re-run review'}
        </button>
      </div>

      {analysis_degraded && (
        <p className="pr-degraded-notice">
          This review used a simplified fallback — the underlying repository data is still accurate.
        </p>
      )}

      <div className="pr-collapsible-stack">
        <CollapsibleSection title="Engineering Assessment" defaultOpen={true}>
          <p className="pr-assessment">{engineering_assessment}</p>
        </CollapsibleSection>

        {flagship_projects.length > 0 && (
          <CollapsibleSection title="Flagship Projects" defaultOpen={true}>
            <div className="pr-flagship-list">
              {flagship_projects.map((fp) => (
                <div key={fp.name} className="pr-flagship-card">
                  <span className="pr-flagship-name">★ {fp.name}</span>
                  <p className="pr-flagship-reason">{fp.reason}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {role_fit.length > 0 && (
          <CollapsibleSection title="Role Fit" defaultOpen={false}>
            <div className="pr-role-list">
              {role_fit.map((r) => <RoleFitRow key={r.role} item={r} />)}
            </div>
          </CollapsibleSection>
        )}

        {engineering_habits.length > 0 && (
          <CollapsibleSection title="Engineering Habits" defaultOpen={false}>
            <div className="pr-habits-grid">
              <div>
                <span className="pr-habits-label pr-habits-label--good">Strengths</span>
                <ul>
                  {engineering_habits.filter((h) => h.is_strength).map((h, i) => (
                    <li key={i}>✓ {h.observation}</li>
                  ))}
                </ul>
              </div>
              <div>
                <span className="pr-habits-label pr-habits-label--gap">Needs work</span>
                <ul>
                  {engineering_habits.filter((h) => !h.is_strength).map((h, i) => (
                    <li key={i}>△ {h.observation}</li>
                  ))}
                </ul>
              </div>
            </div>
          </CollapsibleSection>
        )}

        {skill_confidence_explanations.length > 0 && (
          <CollapsibleSection title="Skill Confidence, Explained" defaultOpen={false}>
            <div className="pr-skill-explain-list">
              {skill_confidence_explanations.map((s) => (
                <div key={s.skill} className="pr-skill-explain-row">
                  <span className="pr-skill-explain-name">{s.skill}</span>
                  <p className="pr-skill-explain-text">{s.explanation}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {recruiter_perspective && (recruiter_perspective.notices?.length > 0 || recruiter_perspective.decision) && (
          <CollapsibleSection title="Recruiter Perspective (20-second skim)" defaultOpen={false}>
            <ul className="pr-recruiter-notices">
              {recruiter_perspective.notices?.map((n, i) => <li key={i}>{n}</li>)}
            </ul>
            {recruiter_perspective.decision && (
              <p className="pr-recruiter-decision">{recruiter_perspective.decision}</p>
            )}
          </CollapsibleSection>
        )}

        {growth_story && (
          <CollapsibleSection title="Growth Story" defaultOpen={false}>
            <p className="pr-growth-story">{growth_story}</p>
          </CollapsibleSection>
        )}

        {resume_integration_suggestions.length > 0 && (
          <CollapsibleSection title="Resume Integration" defaultOpen={false}>
            <ul className="pr-resume-suggestions">
              {resume_integration_suggestions.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </CollapsibleSection>
        )}

        {improvement_roadmap.length > 0 && (
          <CollapsibleSection title="Improvement Roadmap" defaultOpen={false}>
            <ol className="pr-roadmap">
              {improvement_roadmap.map((s, i) => <li key={i}><span>{i + 1}</span>{s}</li>)}
            </ol>
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}

export default PortfolioReviewPanel