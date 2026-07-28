import './CompareProjectsPanel.css'

function CompareProjectsPanel({ comparison }) {
  if (!comparison) return null

  return (
    <section className="compare-projects">
      <div className="compare-projects__header">
        <h2>Compare projects</h2>
        <p className="compare-projects__lead">See which story is strongest for a particular career conversation.</p>
      </div>

      <div className="compare-projects__card">
        <div className="compare-projects__metrics">
          <h3 className="compare-projects__title">{comparison.project_a} vs {comparison.project_b}</h3>
          {comparison.metrics.map((m) => (
            <div className="compare-projects__row" key={m.label}>
              <span className="compare-projects__label">{m.label}</span>
              <span className="compare-projects__winner">{m.winner}</span>
            </div>
          ))}
        </div>

        <div className="compare-projects__recommendation">
          <span className="compare-projects__recommendation-tag">Recommendation</span>
          <p>{comparison.recommendation}</p>
        </div>
      </div>
    </section>
  )
}

export default CompareProjectsPanel