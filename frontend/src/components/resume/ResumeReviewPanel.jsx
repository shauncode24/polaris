import './ResumeReviewPanel.css'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function scoreClass(score) {
  if (score >= 75) return 'high'
  if (score >= 50) return 'mid'
  return 'low'
}

function barColor(score) {
  if (score >= 75) return 'var(--success)'
  if (score >= 50) return 'var(--warning)'
  return 'var(--danger)'
}

export default function ResumeReviewPanel({ review, onRunReview, reviewLoading }) {
  if (!review) {
    return (
      <div className="rrp">
        <div className="rrp__header">
          <span className="rrp__title">Resume Analysis</span>
        </div>
        <div className="rrp__empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--border)' }}>
            <path d="M9 11l3 3 8-8" /><path d="M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9" />
          </svg>
          <p>No review run yet.</p>
          <button className="rrp__empty-btn" onClick={onRunReview} disabled={reviewLoading}>
            {reviewLoading ? 'Running…' : 'Run AI Review'}
          </button>
        </div>
      </div>
    )
  }

  const { overall_score: score, stats, summary, strengths = [], top_priority_fixes = [], bullet_reviews = [], created_at } = review

  return (
    <div className="rrp">
      <div className="rrp__header">
        <span className="rrp__title">Resume Analysis</span>
        {created_at && <span className="rrp__date">Last run {formatDate(created_at)}</span>}
      </div>
      <div className="rrp__body">
        {/* Score */}
        <div className="rrp__score-row">
          <div className={`rrp__score-circle ${scoreClass(score)}`}>{score}</div>
          <div className="rrp__score-meta">
            <div className="rrp__score-label">Overall Resume Score</div>
            <div className="rrp__bar-track">
              <div
                className="rrp__bar-fill"
                style={{ width: `${score}%`, background: barColor(score) }}
              />
            </div>
          </div>
        </div>

        {/* Bullet stats */}
        {stats && (
          <div className="rrp__stats">
            <div className="rrp__stat">
              <div className="rrp__stat-val">{stats.total_bullets}</div>
              <div className="rrp__stat-lbl">Bullets</div>
            </div>
            <div className="rrp__stat">
              <div className="rrp__stat-val" style={{ color: stats.flagged_bullets > 0 ? 'var(--warning)' : 'var(--success)' }}>
                {stats.flagged_bullets}
              </div>
              <div className="rrp__stat-lbl">Flagged</div>
            </div>
            <div className="rrp__stat">
              <div className="rrp__stat-val" style={{ color: stats.missing_metric_count > 0 ? 'var(--danger)' : 'var(--success)' }}>
                {stats.missing_metric_count}
              </div>
              <div className="rrp__stat-lbl">No Metrics</div>
            </div>
          </div>
        )}

        {/* Summary */}
        {summary && <p className="rrp__summary">{summary}</p>}

        {/* Strengths */}
        {strengths.length > 0 && (
          <div>
            <div className="rrp__list-title" style={{ color: 'var(--success)' }}>✓ Strengths</div>
            <div className="rrp__list">
              {strengths.slice(0, 3).map((s, i) => (
                <div key={i} className="rrp__list-item" style={{'--color': 'var(--success)'}}>
                  <span style={{ color: 'var(--success)', marginTop: 1 }}>✓</span>
                  {s}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Priority fixes */}
        {top_priority_fixes.length > 0 && (
          <div>
            <div className="rrp__list-title" style={{ color: 'var(--warning)' }}>⚡ Priority Fixes</div>
            <div className="rrp__list">
              {top_priority_fixes.slice(0, 4).map((f, i) => (
                <div key={i} className="rrp__list-item">
                  <span style={{ color: 'var(--warning)', marginTop: 1 }}>!</span>
                  {f}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Bullet Rewrites */}
        {bullet_reviews && bullet_reviews.filter(br => br.rewrite).length > 0 && (
          <div style={{ marginTop: 8, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <div className="rrp__list-title" style={{ color: 'var(--accent)', marginBottom: 12 }}>🤖 AI Bullet Rewrites</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {bullet_reviews.filter(br => br.rewrite).map((br, i) => (
                <div key={i} style={{ background: 'var(--surface-soft)', padding: 12, borderRadius: 'var(--radius-md)', border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-soft)', textTransform: 'uppercase', marginBottom: 6 }}>
                    {br.source_label}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12.5 }}>
                    <div style={{ color: 'var(--text-soft)', textDecoration: 'line-through' }}>
                      {br.original}
                    </div>
                    <div style={{ color: 'var(--ink)', fontWeight: 500 }}>
                      <span style={{ color: 'var(--success)', marginRight: 4 }}>✦</span>
                      {br.rewrite}
                    </div>
                    {br.rewrite_rationale && (
                      <div style={{ fontSize: 11.5, color: 'var(--text-soft)', fontStyle: 'italic', marginTop: 4 }}>
                        Rationale: {br.rewrite_rationale}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
