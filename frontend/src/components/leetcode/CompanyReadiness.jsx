import { useState } from 'react'
import './CompanyReadiness.css'

function toneFor(pct) {
  if (pct >= 70) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

function Row({ c }) {
  return (
    <div className="cr-row" key={c.company}>
      <div className="cr-row__top">
        <span className="cr-row__name">{c.company}</span>
        <span className="cr-row__pct">{c.readiness_pct}%</span>
      </div>
      <div className="cr-row__track">
        <div className={`cr-row__fill cr-row__fill--${toneFor(c.readiness_pct)}`} style={{ width: `${c.readiness_pct}%` }} />
      </div>
      {c.weak_topics.length > 0 && (
        <span className="cr-row__weak">Weakest: {c.weak_topics.join(', ')}</span>
      )}
    </div>
  )
}

function CompanyReadiness({ companyReadiness }) {
  const [showAll, setShowAll] = useState(false)

  if (!companyReadiness || companyReadiness.length === 0) {
    return (
      <section className="lc-card">
        <h3>Company readiness</h3>
        <p className="lc-empty-text">Sync LeetCode to see readiness estimates against common interview loops.</p>
      </section>
    )
  }

  const sorted = [...companyReadiness].sort((a, b) => b.readiness_pct - a.readiness_pct)
  const isLong = sorted.length > 10
  const visible = showAll || !isLong ? sorted : [...sorted.slice(0, 5), ...sorted.slice(-5)]

  return (
    <section className="lc-card">
      <h3>Company readiness</h3>
      <p className="lc-card__lead">A weighted read of your topic mastery against known interview-loop patterns.</p>
      <div className="cr-list">
        {visible.map((c) => <Row key={c.company} c={c} />)}
      </div>
      {isLong && (
        <button type="button" className="cr-toggle" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show top & bottom only' : `View all ${sorted.length} companies`}
        </button>
      )}
    </section>
  )
}

export default CompanyReadiness