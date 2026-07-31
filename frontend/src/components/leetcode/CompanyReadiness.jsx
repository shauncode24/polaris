import './CompanyReadiness.css'

function toneFor(pct) {
  if (pct >= 70) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

function CompanyReadiness({ companyReadiness }) {
  if (!companyReadiness || companyReadiness.length === 0) {
    return (
      <section className="lc-card">
        <h3>Company readiness</h3>
        <p className="lc-empty-text">Sync LeetCode to see readiness estimates against common interview loops.</p>
      </section>
    )
  }

  return (
    <section className="lc-card">
      <h3>Company readiness</h3>
      <p className="lc-card__lead">A weighted read of your topic mastery against known interview-loop patterns — not a guarantee, a starting point.</p>
      <div className="cr-list">
        {companyReadiness.map((c) => (
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
        ))}
      </div>
    </section>
  )
}

export default CompanyReadiness