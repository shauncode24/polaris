import { IconSparkle } from '../icons/DashboardIcons'
import './AIRecommendationsPanel.css'

// Doc: "Keep. Compress into one compact section... No oversized
// recommendation cards." Same `recommendations` data (RecommendationItem[]
// from recommendations.py) — just a vertical list instead of a 2-column
// grid of padded tiles.
function AIRecommendationsPanel({ recommendations }) {
  if (!recommendations || recommendations.length === 0) return null

  return (
    <section className="ai-recs">
      <div className="ai-recs__header">
        <IconSparkle size={15} />
        <h2>Highest impact</h2>
      </div>
      <ul className="ai-recs__list">
        {recommendations.map((r, i) => (
          <li className="ai-recs__item" key={i}>
            {r.impact != null && r.impact > 0 && <span className="ai-recs__impact">+{r.impact}</span>}
            <span className="ai-recs__text">{r.text}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export default AIRecommendationsPanel