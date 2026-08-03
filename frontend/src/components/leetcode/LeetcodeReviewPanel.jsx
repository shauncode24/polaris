import { useState } from 'react'
import './LeetcodeReviewPanel.css'

// Recruiter Perspective is merged in here as a compact "Recruiter take"
// (Review §"Recruiter Perspective" — one AI-generated insight section
// is enough; it was just another narrative summary of the same data).
function buildRecruiterTake({ totalSolved, topicMastery, blindSpots }) {
  const strong = (topicMastery || [])
    .filter((t) => t.mastery === 'Consistent Practice' || t.mastery === 'Extensive Practice')
    .map((t) => t.topic)
  const missing = blindSpots?.missing_fundamentals || []

  if (!totalSolved) return null
  if (missing.length > 0) {
    return `Strongest in ${strong.length ? strong.slice(0, 2).join(', ') : 'a small set of topics'}. Closing ${missing[0]} would be the highest-leverage next step.`
  }
  return `Strongest in ${strong.length ? strong.slice(0, 2).join(', ') : 'a small set of topics'}. Every fundamental interview topic has at least some evidence.`
}

function Truncated({ text, limit = 220 }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return null
  const isLong = text.length > limit
  const shown = expanded || !isLong ? text : text.slice(0, limit).trimEnd() + '…'
  return (
    <>
      <p className="lcr-text lcr-text--highlight">{shown}</p>
      {isLong && (
        <button type="button" className="lcr-expand" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Show less' : 'Show more'}
        </button>
      )}
    </>
  )
}

function LeetcodeReviewPanel({ review, onRun, loading, totalSolved, topicMastery, blindSpots }) {
  if (!review) {
    return (
      <div className="lcr-panel">
        <div className="lcr-panel__empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--border)' }}>
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
          <p>No AI coach feedback generated yet.</p>
          <button type="button" className="lcr-panel__cta" onClick={onRun} disabled={loading}>
            {loading ? 'Analyzing…' : 'Generate AI Coach Feedback'}
          </button>
        </div>
      </div>
    )
  }

  const {
    interview_coach,
    learning_strategy,
    target_focus_topics = [],
    roadmap_actions = [],
    analysis_degraded,
  } = review

  const recruiterTake = buildRecruiterTake({ totalSolved, topicMastery, blindSpots })

  return (
    <div className="lcr-container">
      <div className="lcr-header">
        <span className="lcr-subtitle">Holistic review comparing LeetCode DSA and GitHub engineering signals</span>
        <button type="button" className="lcr-refresh" onClick={onRun} disabled={loading}>
          {loading ? 'Analyzing…' : '↻ Re-run coach'}
        </button>
      </div>

      {analysis_degraded && (
        <p className="lcr-degraded-notice">
          This coach review used a simplified fallback — your sync history is still complete.
        </p>
      )}

      <div className="lcr-section">
        <div className="lcr-card-inner">
          <div className="lcr-badge">Executive Summary</div>
          <Truncated text={interview_coach} />
        </div>
      </div>

      <div className="lcr-section">
        <div className="lcr-card-inner">
          <div className="lcr-badge">Learning Strategy</div>
          <Truncated text={learning_strategy} limit={180} />

          {target_focus_topics.length > 0 && (
            <div className="lcr-focus-topics">
              <span className="lcr-focus-label">Priority focus topics:</span>
              <div className="lcr-focus-tags">
                {target_focus_topics.map((t) => (
                  <span key={t} className="lcr-focus-tag">{t}</span>
                ))}
              </div>
            </div>
          )}

          {roadmap_actions.length > 0 && (
            <div className="lcr-roadmap">
              <span className="lcr-focus-label">Action Plan:</span>
              <ul className="lcr-roadmap-list">
                {roadmap_actions.slice(0, 4).map((action, i) => (
                  <li key={i} className="lcr-roadmap-item">
                    <span className="lcr-roadmap-step">{i + 1}</span>
                    <span className="lcr-roadmap-text">{action}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {recruiterTake && (
        <div className="lcr-section">
          <div className="lcr-card-inner lcr-card-inner--recruiter">
            <div className="lcr-badge lcr-badge--muted">Recruiter take</div>
            <p className="lcr-text">{recruiterTake}</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default LeetcodeReviewPanel