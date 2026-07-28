import { IconSparkle } from '../icons/DashboardIcons'
import './AIRecommendationsPanel.css'

function AIRecommendationsPanel({ recommendations }) {
  if (!recommendations || recommendations.length === 0) return null

  return (
    <section className="ai-recs">
      <h2>AI recommendations</h2>
      <div className="ai-recs__grid">
        {recommendations.map((r, i) => (
          <div className="ai-recs__item" key={i}>
            <IconSparkle size={15} />
            <span>{r.text}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export default AIRecommendationsPanel