import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './PortfolioReviewPanel.css'

function RoleFitRow({ item }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="pr-role-row" onClick={() => setOpen((v) => !v)} role="button" tabIndex={0}>
      <div className="pr-role-row__head">
        <span className="pr-role-name">{item.role}</span>
        <span className="pr-role-stars">
          {'★'.repeat(item.rating)}{'☆'.repeat(Math.max(0, 5 - item.rating))}
        </span>
      </div>
      {open && <p className="pr-role-rationale">{item.rationale}</p>}
    </div>
  )
}

function PortfolioReviewPanel({ review, onRun, loading, recommendations = [] }) {
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
    engineering_habits = [], recruiter_perspective,
    resume_integration_suggestions = [], growth_story,
    improvement_roadmap = [], analysis_degraded,
  } = review

  const strengths = engineering_habits.filter((h) => h.is_strength)
  const weaknesses = engineering_habits.filter((h) => !h.is_strength)
  const topFlagship = flagship_projects.slice(0, 3)

  // Next Steps = deterministic recommendations first (real, ranked-by-impact
  // actions), then any LLM roadmap items not already covered by them.
  const recActions = new Set(recommendations.map((r) => r.action?.toLowerCase()))
  const roadmapExtras = improvement_roadmap.filter(
    (s) => !recActions.has(String(s).toLowerCase())
  )
  const hasNextSteps = recommendations.length > 0 || roadmapExtras.length > 0

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
        <CollapsibleSection title="Executive Summary" dense defaultOpen={true}>
          <p className="pr-assessment">{engineering_assessment}</p>
        </CollapsibleSection>

        {strengths.length > 0 && (
          <CollapsibleSection title="Strengths" dense defaultOpen={true}>
            <ul className="pr-checklist pr-checklist--good">
              {strengths.map((h, i) => <li key={i}>✓ {h.observation}</li>)}
            </ul>
          </CollapsibleSection>
        )}

        {weaknesses.length > 0 && (
          <CollapsibleSection title="Weaknesses" dense defaultOpen={true}>
            <ul className="pr-checklist pr-checklist--gap">
              {weaknesses.map((h, i) => <li key={i}>△ {h.observation}</li>)}
            </ul>
          </CollapsibleSection>
        )}

        {topFlagship.length > 0 && (
          <CollapsibleSection title="Flagship Projects" dense defaultOpen={true}>
            <div className="pr-flagship-list">
              {topFlagship.map((fp) => (
                <div key={fp.name} className="pr-flagship-card">
                  <span className="pr-flagship-name">★ {fp.name}</span>
                  <p className="pr-flagship-reason">{fp.reason}</p>
                </div>
              ))}
            </div>
          </CollapsibleSection>
        )}

        {role_fit.length > 0 && (
          <CollapsibleSection title="Role Fit" subtitle="Tap a role to see the rationale" dense defaultOpen={false}>
            <div className="pr-role-list">
              {role_fit.map((r) => <RoleFitRow key={r.role} item={r} />)}
            </div>
          </CollapsibleSection>
        )}

        {hasNextSteps && (
          <CollapsibleSection title="Next Steps" dense defaultOpen={true}>
            <ol className="pr-next-steps">
              {recommendations.slice(0, 4).map((r, i) => (
                <li key={`rec-${i}`}>
                  <span>{i + 1}</span>
                  <span>{r.action}<em className="pr-next-steps__impact">+{r.impact}</em></span>
                </li>
              ))}
              {roadmapExtras.map((s, i) => (
                <li key={`road-${i}`}>
                  <span>{recommendations.slice(0, 4).length + i + 1}</span>
                  <span>{s}</span>
                </li>
              ))}
            </ol>
          </CollapsibleSection>
        )}

        {(recruiter_perspective?.notices?.length > 0 || recruiter_perspective?.decision || growth_story || resume_integration_suggestions.length > 0) && (
          <CollapsibleSection title="More Details" subtitle="Recruiter read, growth story, resume integration" dense defaultOpen={false}>
            {recruiter_perspective && (recruiter_perspective.notices?.length > 0 || recruiter_perspective.decision) && (
              <div className="pr-more-block">
                <span className="pr-more-block__label">Recruiter Perspective (20-second skim)</span>
                <ul className="pr-recruiter-notices">
                  {recruiter_perspective.notices?.map((n, i) => <li key={i}>{n}</li>)}
                </ul>
                {recruiter_perspective.decision && (
                  <p className="pr-recruiter-decision">{recruiter_perspective.decision}</p>
                )}
              </div>
            )}

            {growth_story && (
              <div className="pr-more-block">
                <span className="pr-more-block__label">Growth Story</span>
                <p className="pr-growth-story">{growth_story}</p>
              </div>
            )}

            {resume_integration_suggestions.length > 0 && (
              <div className="pr-more-block">
                <span className="pr-more-block__label">Resume Integration</span>
                <ul className="pr-resume-suggestions">
                  {resume_integration_suggestions.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </div>
            )}
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}

export default PortfolioReviewPanel