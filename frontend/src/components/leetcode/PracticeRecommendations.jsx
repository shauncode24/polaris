import './PracticeRecommendations.css'

function PracticeRecommendations({ recommendations }) {
  if (!recommendations || recommendations.length === 0) {
    return (
      <section className="lc-card">
        <h3>Practice recommendations</h3>
        <p className="lc-empty-text">No recommendations available at this time. Keep solving problems!</p>
      </section>
    )
  }

  return (
    <section className="lc-card">
      <h3>Practice recommendations</h3>
      <p className="lc-card__lead">Customized checklist to optimize your interview readiness.</p>

      <div className="pr-list">
        {recommendations.map((rec, idx) => {
          const priority = rec.priority || 'Low'
          const priorityClass = `pr-item__badge--${priority.toLowerCase()}`
          return (
            <div key={idx} className="pr-item">
              <span className={`pr-item__badge ${priorityClass}`}>
                {priority}
              </span>
              <div className="pr-item__body">
                <span className="pr-item__action">{rec.action}</span>
                <span className="pr-item__reason">{rec.reason}</span>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default PracticeRecommendations