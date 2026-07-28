import './AIRecommendations.css'

function AIRecommendations({ insightRecommendations }) {
  const items = (insightRecommendations || []).slice(0, 5)
  return (
    <section className="gh-recs">
      <h2>Recommendations</h2>
      {items.length === 0 ? (
        <p className="gh-recs__empty">Nothing urgent — your repositories look well maintained.</p>
      ) : (
        <ul className="gh-recs__list">
          {items.map((rec, i) => (
            <li key={i} className="gh-recs__item">
              <span className="gh-recs__icon">✓</span>
              <span>{rec.action}</span>
              <span className="gh-recs__impact">+{rec.impact}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default AIRecommendations