import { useState } from 'react'
import './GitHubHealthCards.css'

function ScoreChip({ label, value, tone, sentence, progress, breakdown }) {
  const [open, setOpen] = useState(false)
  const hasProgress = typeof progress === 'number'

  return (
    <button
      type="button"
      className={`gh-chip ${open ? 'gh-chip--open' : ''}`}
      onClick={() => setOpen((v) => !v)}
      aria-expanded={open}
    >
      <div className="gh-chip__top">
        <span className="gh-chip__label">{label}</span>
        <span className={`gh-chip__value gh-chip__value--${tone}`}>{value}</span>
      </div>

      {sentence && <p className="gh-chip__sentence">{sentence}</p>}

      {hasProgress && (
        <div className="gh-chip__track">
          <div
            className={`gh-chip__fill gh-chip__fill--${tone}`}
            style={{ width: `${Math.max(4, Math.min(100, progress))}%` }}
          />
        </div>
      )}

      <span className="gh-chip__toggle">
        {open ? 'Hide details' : 'How is this calculated?'}
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          className={`gh-chip__toggle-icon ${open ? 'gh-chip__toggle-icon--open' : ''}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </span>

      {open && breakdown && (
        <div className="gh-chip__breakdown">
          {Object.entries(breakdown).map(([k, v]) => (
            <div key={k} className="gh-chip__breakdown-row">
              <span>{k}</span><span>{v}</span>
            </div>
          ))}
        </div>
      )}
    </button>
  )
}

function GitHubHealthCards({ overall, overallLabel, overallTone, metrics }) {
  return (
    <div className="gh-health-v2">
      <div className={`gh-health-v2__hero gh-health-v2__hero--${overallTone}`}>
        <span className="gh-health-v2__hero-label">GitHub Portfolio Score</span>
        <span className="gh-health-v2__hero-value">{overall}</span>
        <span className="gh-health-v2__hero-tag">{overallLabel}</span>
        <div className="gh-health-v2__hero-track">
          <div
            className={`gh-health-v2__hero-fill gh-health-v2__hero-fill--${overallTone}`}
            style={{ width: `${Math.max(4, Math.min(100, overall))}%` }}
          />
        </div>
        <span className="gh-health-v2__hero-hint">Average across activity, docs, and code quality</span>
      </div>
      <div className="gh-health-v2__chips">
        {metrics.map((m) => (
          <ScoreChip key={m.label} {...m} />
        ))}
      </div>
    </div>
  )
}

export default GitHubHealthCards