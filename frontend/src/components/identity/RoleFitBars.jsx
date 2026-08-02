// frontend/src/components/identity/RoleFitBars.jsx
import './RoleFitBars.css'

function toneFor(pct) {
  if (pct >= 70) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

// FIX: the backend's RoleFitResult shape is {role, rating (1-5), rationale}.
// This previously read a `match_pct` field that the API never returns,
// so every bar silently rendered as 0%/undefined. Now derives a percentage
// from the real 1-5 rating and also surfaces the rationale, which was
// computed by the role-fit LLM call but never shown anywhere.
function RoleFitBars({ roleFit = [] }) {
  if (roleFit.length === 0) {
    return <p className="identity-empty-text">Not enough evidence yet to compute role fit.</p>
  }

  return (
    <div className="rolefit-bars">
      {roleFit.map((r) => {
        const pct = Math.round((r.rating / 5) * 100)
        return (
          <div className="rolefit-bars__row" key={r.role}>
            <div className="rolefit-bars__row-top">
              <span className="rolefit-bars__label">{r.role}</span>
              <span className="rolefit-bars__pct">{r.rating}/5</span>
            </div>
            <div className="rolefit-bars__track">
              <div
                className={`rolefit-bars__fill rolefit-bars__fill--${toneFor(pct)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            {r.rationale && <p className="rolefit-bars__rationale">{r.rationale}</p>}
          </div>
        )
      })}
    </div>
  )
}

export default RoleFitBars