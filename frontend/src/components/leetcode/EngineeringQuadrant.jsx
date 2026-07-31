import './EngineeringQuadrant.css'

const QUADRANT_POSITION = {
  'Well-Rounded': { top: '10%', left: '65%' },
  'Builder': { top: '65%', left: '65%' },
  'Solver': { top: '10%', left: '15%' },
  'Foundational': { top: '65%', left: '15%' },
}

function EngineeringQuadrant({ quadrant }) {
  if (!quadrant) {
    return (
      <section className="lc-card">
        <h3>Engineering maturity quadrant</h3>
        <p className="lc-empty-text">Sync both LeetCode and GitHub to see how your algorithmic and practical engineering evidence compare.</p>
      </section>
    )
  }

  const { leetcode_score, github_score, quadrant_label, description } = quadrant
  const pos = QUADRANT_POSITION[quadrant_label] || QUADRANT_POSITION['Foundational']

  return (
    <section className="lc-card eq-card">
      <h3>Engineering maturity quadrant</h3>
      <p className="lc-card__lead">Algorithmic reasoning (LeetCode) vs. practical engineering (GitHub) — not a score, a shape.</p>

      <div className="eq-grid">
        <div className="eq-grid__axis-y">GitHub score</div>
        <div className="eq-grid__plane">
          <span className="eq-grid__label eq-grid__label--tl">Solver</span>
          <span className="eq-grid__label eq-grid__label--tr">Well-Rounded</span>
          <span className="eq-grid__label eq-grid__label--bl">Foundational</span>
          <span className="eq-grid__label eq-grid__label--br">Builder</span>
          <div className="eq-grid__dot" style={{ top: pos.top, left: pos.left }} title={quadrant_label} />
        </div>
      </div>
      <div className="eq-grid__axis-x">LeetCode score</div>

      <div className="eq-summary">
        <div className="eq-summary__scores">
          <span><strong>{leetcode_score}</strong> LeetCode</span>
          <span><strong>{github_score}</strong> GitHub</span>
        </div>
        <span className="eq-summary__label">{quadrant_label}</span>
      </div>
      <p className="eq-description">{description}</p>
    </section>
  )
}

export default EngineeringQuadrant