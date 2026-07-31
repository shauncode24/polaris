import './TechDepthGrid.css'

function toneFor(score) {
  if (score >= 80) return 'deep'
  if (score >= 55) return 'working'
  if (score >= 30) return 'applied'
  return 'surface'
}

function TechDepthGrid({ highlights = [] }) {
  if (highlights.length === 0) {
    return <p className="identity-empty-text">Sync GitHub to see technology depth.</p>
  }

  return (
    <div className="tech-depth-grid">
      {highlights.map((h) => (
        <div className="tech-depth-grid__card" key={h.technology}>
          <div className="tech-depth-grid__row">
            <span className="tech-depth-grid__name">{h.technology}</span>
            <span className={`tech-depth-grid__badge tech-depth-grid__badge--${toneFor(h.score)}`}>{h.label}</span>
          </div>
          <div className="tech-depth-grid__track">
            <div className={`tech-depth-grid__fill tech-depth-grid__fill--${toneFor(h.score)}`} style={{ width: `${h.score}%` }} />
          </div>
          <span className="tech-depth-grid__detail">{h.repo_count} repo{h.repo_count === 1 ? '' : 's'} · score {h.score}/100</span>
        </div>
      ))}
    </div>
  )
}

export default TechDepthGrid