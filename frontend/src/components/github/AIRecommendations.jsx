import './AIRecommendations.css'

function buildRecommendations(repositories, insightRecommendations) {
  const items = []
  const byScore = [...repositories].sort(
    (a, b) => (b.project_score?.overall || 0) - (a.project_score?.overall || 0)
  )

  for (const repo of byScore) {
    if (items.length >= 4) break
    if (!repo.has_tests) items.push(`Add unit tests to ${repo.name}`)
    else if (!repo.has_readme) items.push(`Improve the ${repo.name} README`)
    else if (!repo.has_ci) items.push(`Add CI/CD to ${repo.name}`)
  }

  if (items.length < 4) {
    for (const rec of insightRecommendations || []) {
      if (items.length >= 5) break
      const text = `${rec.reason}${rec.project ? ` — ${rec.project}` : ''}`
      if (!items.includes(text)) items.push(text)
    }
  }

  return items.slice(0, 5)
}

function AIRecommendations({ repositories, insightRecommendations }) {
  const items = buildRecommendations(repositories, insightRecommendations)

  return (
    <section className="gh-recs">
      <h2>AI recommendations</h2>
      {items.length === 0 ? (
        <p className="gh-recs__empty">Nothing urgent — your repositories look well maintained.</p>
      ) : (
        <ul className="gh-recs__list">
          {items.map((text, i) => (
            <li key={i} className="gh-recs__item">
              <span className="gh-recs__icon">✓</span>
              {text}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default AIRecommendations