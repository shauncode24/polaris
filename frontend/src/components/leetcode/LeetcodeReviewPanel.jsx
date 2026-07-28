import './LeetcodeReviewPanel.css'

function LeetcodeReviewPanel({ review, onRun, loading }) {
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
          <div className="lcr-badge">Interview Coach</div>
          <p className="lcr-text lcr-text--highlight">{interview_coach}</p>
        </div>
      </div>

      <div className="lcr-section">
        <div className="lcr-card-inner">
          <div className="lcr-badge">Learning Strategy</div>
          <p className="lcr-text">{learning_strategy}</p>

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
              <span className="lcr-focus-label">Action Roadmap:</span>
              <ul className="lcr-roadmap-list">
                {roadmap_actions.map((action, i) => (
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
    </div>
  )
}

export default LeetcodeReviewPanel
