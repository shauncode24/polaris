import Card from '../common/Card'
import './SignalsGapsPanel.css'

function SignalsGapsPanel({ strongestSignals = [], biggestGaps = [], contradictions = [] }) {
  return (
    <div className="signals-gaps">
      <Card className="signals-gaps__col">
        <h3 className="signals-gaps__title signals-gaps__title--strong">Strongest Signals</h3>
        {strongestSignals.length === 0 ? (
          <p className="identity-empty-text">Nothing evidenced yet.</p>
        ) : (
          <ul className="signals-gaps__list">
            {strongestSignals.map((s, i) => (
              <li key={i} className="signals-gaps__item signals-gaps__item--strong">{s}</li>
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
              <li key={i} className="signals-gaps__item signals-gaps__item--gap">{g}</li>
            ))}
          </ul>
        )}
      </Card>

      {contradictions.length > 0 && (
        <Card className="signals-gaps__col signals-gaps__col--full">
          <h3 className="signals-gaps__title signals-gaps__title--warn">Worth Reconciling</h3>
          <ul className="signals-gaps__list">
            {contradictions.map((c, i) => (
              <li key={i} className="signals-gaps__item signals-gaps__item--warn">{c}</li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

export default SignalsGapsPanel