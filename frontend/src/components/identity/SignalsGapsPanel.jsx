import Card from '../common/Card'
import './SignalsGapsPanel.css'

function SignalsGapsPanel({ strongestSignals = [], biggestGaps = [], contradictions = [] }) {
  const renderClaim = (item, type) => {
    if (typeof item === 'string') {
      return <span className="signals-gaps__text">{item}</span>
    }

    const { statement, kind, grounded_in } = item || {}
    const isFact = kind === 'fact'

    return (
      <div className="signals-gaps__claim-container">
        <div className="signals-gaps__claim">
          <span className="signals-gaps__text">{statement}</span>
          {isFact && (
            <span className={`signals-gaps__badge signals-gaps__badge--${type}`}>
              Fact
            </span>
          )}
        </div>
        {isFact && grounded_in && (
          <span className="signals-gaps__grounded">
            🔍 {grounded_in}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="signals-gaps">
      <Card className="signals-gaps__col">
        <h3 className="signals-gaps__title signals-gaps__title--strong">Strongest Signals</h3>
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
        <h3 className="signals-gaps__title signals-gaps__title--gap">Biggest Gaps</h3>
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

      {contradictions.length > 0 && (
        <Card className="signals-gaps__col signals-gaps__col--full">
          <h3 className="signals-gaps__title signals-gaps__title--warn">Worth Reconciling</h3>
          <ul className="signals-gaps__list">
            {contradictions.map((c, i) => (
              <li key={i} className="signals-gaps__item signals-gaps__item--warn">
                {renderClaim(c, 'warn')}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

export default SignalsGapsPanel