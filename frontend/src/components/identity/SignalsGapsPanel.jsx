// frontend/src/components/identity/SignalsGapsPanel.jsx
import Card from '../common/Card'
import './SignalsGapsPanel.css'

function renderClaim(item, type) {
  if (typeof item === 'string') {
    return <span className="signals-gaps__text">{item}</span>
  }

  const { statement, kind, grounded_in } = item || {}
  const isFact = kind === 'fact'

  return (
    <div className="signals-gaps__claim-container">
      <div className="signals-gaps__claim">
        <span className="signals-gaps__text">{statement}</span>
        {isFact && <span className={`signals-gaps__badge signals-gaps__badge--${type}`}>Fact</span>}
      </div>
      {isFact && grounded_in && <span className="signals-gaps__grounded">🔍 {grounded_in}</span>}
    </div>
  )
}

// Renamed per the redesign: "Strongest Signals" -> "Evidence Driving
// This Identity", "Biggest Gaps" -> "Identity Weaknesses". Contradictions
// moved into IdentityInsights so this panel stays focused on the two
// things a user reads first, instead of a three-way grid.
function SignalsGapsPanel({ strongestSignals = [], biggestGaps = [] }) {
  return (
    <div className="signals-gaps">
      <Card className="signals-gaps__col">
        <h3 className="signals-gaps__title signals-gaps__title--strong">Evidence Driving This Identity</h3>
        {strongestSignals.length === 0 ? (
          <p className="identity-empty-text">Nothing evidenced yet.</p>
        ) : (
          <ul className="signals-gaps__list">
            {strongestSignals.map((s, i) => (
              <li key={i} className="signals-gaps__item signals-gaps__item--strong">
                {renderClaim(s, 'strong')}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="signals-gaps__col">
        <h3 className="signals-gaps__title signals-gaps__title--gap">Identity Weaknesses</h3>
        {biggestGaps.length === 0 ? (
          <p className="identity-empty-text">No significant gaps flagged.</p>
        ) : (
          <ul className="signals-gaps__list">
            {biggestGaps.map((g, i) => (
              <li key={i} className="signals-gaps__item signals-gaps__item--gap">
                {renderClaim(g, 'gap')}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}

export default SignalsGapsPanel