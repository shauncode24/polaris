import { useState } from 'react'
import './GitHubHealthCards.css'

function ScoreChip({ label, value, tone, breakdown }) {
  const [open, setOpen] = useState(false)
  return (
    <button type="button" className="gh-chip" onClick={() => setOpen((v) => !v)}>
      <div className="gh-chip__top">
        <span className="gh-chip__label">{label}</span>
        <span className={`gh-chip__value gh-chip__value--${tone}`}>{value}</span>
      </div>
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

function GitHubHealthCards({ overall, overallLabel, overallTone, breakdown, metrics }) {
  return (
    <div className="gh-health-v2">
      <div className={`gh-health-v2__hero gh-health-v2__hero--${overallTone}`}>
        <span className="gh-health-v2__hero-label">Engineering Health</span>
        <span className="gh-health-v2__hero-value">{overall}</span>
        <span className="gh-health-v2__hero-tag">{overallLabel}</span>
        <span className="gh-health-v2__hero-hint">Tap any metric below to see how it's calculated</span>
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