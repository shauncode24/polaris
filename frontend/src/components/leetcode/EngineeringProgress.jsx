// frontend/src/components/leetcode/EngineeringProgress.jsx
// Merges Engineering Maturity Quadrant (shrunk ~55%) + Quadrant History
// side-by-side, per Review §"Engineering Maturity Quadrant".
import './EngineeringProgress.css'

const QUADRANT_POSITION = {
  'Well-Rounded': { top: '10%', left: '65%' },
  'Builder': { top: '65%', left: '65%' },
  'Solver': { top: '10%', left: '15%' },
  'Foundational': { top: '65%', left: '15%' },
}

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const SOURCE_LABEL = {
  'leetcode sync': 'LC sync',
  'leetcode manual submission': 'Manual',
  'github sync': 'GH sync',
}

function EngineeringProgress({ quadrant, history }) {
  if (!quadrant && (!history || history.length < 2)) {
    return (
      <section className="lc-card">
        <h3>Engineering progress</h3>
        <p className="lc-empty-text">Sync both LeetCode and GitHub to see your algorithmic-vs-practical engineering shape over time.</p>
      </section>
    )
  }

  const pos = quadrant ? (QUADRANT_POSITION[quadrant.quadrant_label] || QUADRANT_POSITION['Foundational']) : null
  const maxScore = history && history.length
    ? Math.max(...history.flatMap((h) => [h.leetcode_score, h.github_score]), 1)
    : 1

  return (
    <section className="lc-card ep-card">
      <h3>Engineering progress</h3>
      <p className="lc-card__lead">Algorithmic reasoning vs. practical engineering — and how it's moved across syncs.</p>

      <div className="ep-grid">
        <div className="ep-quadrant">
          {quadrant ? (
            <>
              <div className="ep-plane">
                <span className="ep-plane-label ep-plane-label--tl">Solver</span>
                <span className="ep-plane-label ep-plane-label--tr">Well-Rounded</span>
                <span className="ep-plane-label ep-plane-label--bl">Foundational</span>
                <span className="ep-plane-label ep-plane-label--br">Builder</span>
                <div className="ep-dot" style={{ top: pos.top, left: pos.left }} title={quadrant.quadrant_label} />
              </div>
              <div className="ep-quadrant-footer">
                <span><strong>{quadrant.leetcode_score}</strong> LC</span>
                <span><strong>{quadrant.github_score}</strong> GH</span>
                <span className="ep-quadrant-tag">{quadrant.quadrant_label}</span>
              </div>
            </>
          ) : (
            <p className="lc-empty-text">Sync GitHub too, to unlock this.</p>
          )}
        </div>

        <div className="ep-history">
          {!history || history.length < 2 ? (
            <p className="lc-empty-text">Sync again to start tracking movement over time.</p>
          ) : (
            <>
              {history.map((h, i) => (
                <div className="ep-hrow" key={i}>
                  <div className="ep-hrow-meta">
                    <span className="ep-hrow-date">{formatDate(h.computed_at)}</span>
                    <span className="ep-hrow-source">{SOURCE_LABEL[h.source_event] || h.source_event}</span>
                  </div>
                  <div className="ep-hrow-bars">
                    <div className="ep-bar ep-bar--lc" style={{ width: `${Math.max(4, (h.leetcode_score / maxScore) * 100)}%` }} title={`LC: ${h.leetcode_score}`} />
                    <div className="ep-bar ep-bar--gh" style={{ width: `${Math.max(4, (h.github_score / maxScore) * 100)}%` }} title={`GH: ${h.github_score}`} />
                  </div>
                </div>
              ))}
              <div className="ep-legend">
                <span><span className="ep-dot-legend ep-dot-legend--lc" /> LeetCode</span>
                <span><span className="ep-dot-legend ep-dot-legend--gh" /> GitHub</span>
              </div>
            </>
          )}
        </div>
      </div>
      {quadrant?.description && <p className="ep-description">{quadrant.description}</p>}
    </section>
  )
}

export default EngineeringProgress