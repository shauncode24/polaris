// frontend/src/components/identity/RoleFitBars.jsx
import { useState } from 'react'
import './RoleFitBars.css'

function Stars({ rating }) {
  return (
    <span className="rolefit-cards__stars" aria-label={`${rating} out of 5`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <span key={n} className={n <= rating ? 'rolefit-cards__star rolefit-cards__star--on' : 'rolefit-cards__star'}>★</span>
      ))}
    </span>
  )
}

function toneFor(rating) {
  if (rating >= 4) return 'strong'
  if (rating >= 3) return 'partial'
  return 'weak'
}

// Redesigned from always-open progress bars + paragraphs into compact,
// tappable cards — rationale is now expand-on-demand per card, which
// was the single biggest length contributor in the old layout.
// Architecture maturity (previously its own separate section elsewhere
// on the page) is folded in here as one line, since it's really a
// footnote to role fit, not its own module.
function RoleFitBars({ roleFit = [], architectureMaturity }) {
  const [expanded, setExpanded] = useState(null)

  if (roleFit.length === 0) {
    return <p className="identity-empty-text">Not enough evidence yet to compute role fit.</p>
  }

  return (
    <div className="rolefit-cards">
      <div className="rolefit-cards__grid">
        {roleFit.map((r) => {
          const isOpen = expanded === r.role
          return (
            <button
              type="button"
              key={r.role}
              className={`rolefit-cards__card rolefit-cards__card--${toneFor(r.rating)} ${isOpen ? 'rolefit-cards__card--open' : ''}`}
              onClick={() => setExpanded(isOpen ? null : r.role)}
              aria-expanded={isOpen}
            >
              <span className="rolefit-cards__role">{r.role}</span>
              <Stars rating={r.rating} />
              {isOpen && r.rationale && <span className="rolefit-cards__rationale">{r.rationale}</span>}
            </button>
          )
        })}
      </div>

      {architectureMaturity?.maturity_score != null && (
        <p className="rolefit-cards__footer">
          Architecture maturity: <strong>{architectureMaturity.maturity_score}/100</strong> — {architectureMaturity.maturity_label}
        </p>
      )}
    </div>
  )
}

export default RoleFitBars