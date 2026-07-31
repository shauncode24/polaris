import './RoleFitBars.css'

function toneFor(pct) {
  if (pct >= 70) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

function RoleFitBars({ roleFit = [] }) {
  if (roleFit.length === 0) {
    return <p className="identity-empty-text">Not enough evidence yet to compute role fit.</p>
  }

  return (
    <div className="rolefit-bars">
      {roleFit.map((r) => (
        <div className="rolefit-bars__row" key={r.role}>
          <div className="rolefit-bars__row-top">
            <span className="rolefit-bars__label">{r.role}</span>
            <span className="rolefit-bars__pct">{r.match_pct}%</span>
          </div>
          <div className="rolefit-bars__track">
            <div
              className={`rolefit-bars__fill rolefit-bars__fill--${toneFor(r.match_pct)}`}
              style={{ width: `${r.match_pct}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

export default RoleFitBars