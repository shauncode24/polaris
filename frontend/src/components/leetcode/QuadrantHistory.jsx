import './QuadrantHistory.css'

function formatDate(iso) {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const SOURCE_LABEL = {
  'leetcode sync': 'LeetCode sync',
  'leetcode manual submission': 'Manual entry',
  'github sync': 'GitHub sync',
}

function QuadrantHistory({ history }) {
  if (!history || history.length < 2) {
    return (
      <section className="lc-card">
        <h3>Quadrant history</h3>
        <p className="lc-empty-text">Sync again after some practice or GitHub activity to start seeing how your quadrant shifts over time.</p>
      </section>
    )
  }

  const maxScore = Math.max(...history.flatMap((h) => [h.leetcode_score, h.github_score]), 1)

  return (
    <section className="lc-card">
      <h3>Quadrant history</h3>
      <p className="lc-card__lead">How your LeetCode and GitHub scores have moved across syncs.</p>
      <div className="qh-list">
        {history.map((h, i) => (
          <div className="qh-row" key={i}>
            <div className="qh-row__meta">
              <span className="qh-row__date">{formatDate(h.computed_at)}</span>
              <span className="qh-row__source">{SOURCE_LABEL[h.source_event] || h.source_event}</span>
              <span className="qh-row__label">{h.quadrant_label}</span>
            </div>
            <div className="qh-row__bars">
              <div className="qh-bar qh-bar--lc" style={{ width: `${Math.max(4, (h.leetcode_score / maxScore) * 100)}%` }} title={`LeetCode: ${h.leetcode_score}`} />
              <div className="qh-bar qh-bar--gh" style={{ width: `${Math.max(4, (h.github_score / maxScore) * 100)}%` }} title={`GitHub: ${h.github_score}`} />
            </div>
          </div>
        ))}
      </div>
      <div className="qh-legend">
        <span><span className="qh-dot qh-dot--lc" /> LeetCode score</span>
        <span><span className="qh-dot qh-dot--gh" /> GitHub score</span>
      </div>
    </section>
  )
}

export default QuadrantHistory