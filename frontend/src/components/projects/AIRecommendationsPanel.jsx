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
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
              <IconSparkle size={15} />
              <span className="ai-recs__text">{r.text}</span>
            </div>
            {r.impact != null && r.impact > 0 && (
              <span className="ai-recs__impact">+{r.impact} pts</span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

export default AIRecommendationsPanel