import CollapsibleSection from '../common/CollapsibleSection'
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

function sanitizeText(text) {
  if (!text) return ''
  let clean = text.replace(/\(\s*(?:exp|proj)_[a-f0-9\-]{32,36}_\d+(?:\s*,\s*(?:exp|proj)_[a-f0-9\-]{32,36}_\d+)*\s*\)/gi, '')
  const rawIdRegex = /['"]?(?:exp|proj)_[a-f0-9\-]{32,36}_\d+['"]?/gi
  clean = clean.replace(rawIdRegex, '')
  clean = clean.replace(/\s+/g, ' ')
  clean = clean.replace(/\s*\(\s*\)/g, '')
  clean = clean.replace(/,\s*\./g, '.')
  clean = clean.replace(/\s*,\s*,/g, ',')
  return clean.trim().replace(/^,\s*/, '').replace(/,\s*$/, '')
}

export default function ResumeReviewPanel({ review, onRunReview, reviewLoading }) {
  if (!review) {
    return (
      <div className="rrp">
        <div className="rrp__header">
          <span className="rrp__title">Resume AI Review</span>
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

  const { overall_score: score, stats, summary, strengths = [], top_priority_fixes = [], bullet_reviews = [], created_at, analysis_degraded } = review

  return (
    <div className="rrp-container">
      <div className="rrp__header-summary">
        <h3 className="rrp__title-main">AI Review Report</h3>
        {created_at && <span className="rrp__date">Last run {formatDate(created_at)}</span>}
      </div>

      <div className="rrp__collapsible-stack">
        <CollapsibleSection title="AI Review Summary" defaultOpen={true}>
          <div className="rrp__score-section">
            {/* Score */}
            <div className="rrp__score-row">
              <div className={`rrp__score-circle ${scoreClass(score)}`}>{score}</div>
              <div className="rrp__score-meta">
                <div className="rrp__score-label">Overall Resume Score</div>
                <div className="rrp__bar-track">
                  <div
                    className="rrppm__bar-fill"
                    style={{ width: `${score}%`, background: barColor(score), height: '100%', borderRadius: 'var(--radius-pill)', transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)' }}
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
                <div className="rrp__stat">
                  <div className="rrp__stat-val" style={{ color: stats.weak_verb_count > 0 ? 'var(--warning)' : 'var(--success)' }}>
                    {stats.weak_verb_count ?? 0}
                  </div>
                  <div className="rrp__stat-lbl">Weak Verbs</div>
                </div>
                <div className="rrp__stat">
                  <div className="rrp__stat-val" style={{ color: stats.passive_voice_count > 0 ? 'var(--warning)' : 'var(--success)' }}>
                    {stats.passive_voice_count ?? 0}
                  </div>
                  <div className="rrp__stat-lbl">Passive Voice</div>
                </div>
              </div>
            )}

            {/* Summary */}
            {summary && <p className="rrp__summary">{sanitizeText(summary)}</p>}

            {/* Strengths */}
            {strengths.length > 0 && (
              <div>
                <div className="rrp__list-title" style={{ color: 'var(--success)' }}>✓ Strengths</div>
                <div className="rrp__list">
                  {strengths.slice(0, 3).map((s, i) => (
                    <div key={i} className="rrp__list-item" style={{'--color': 'var(--success)'}}>
                      <span style={{ color: 'var(--success)', marginTop: 1 }}>✓</span>
                      {sanitizeText(s)}
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
                      {sanitizeText(f)}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Degraded warning */}
            {analysis_degraded && (
              <div className="rrp__degraded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Review analysis degraded — showing deterministic fallback.
              </div>
            )}
          </div>
        </CollapsibleSection>

        {/* Bullet Rewrites */}
        {bullet_reviews && bullet_reviews.filter(br => br.rewrite).length > 0 && (
          <CollapsibleSection title="AI Bullet Rewrites" defaultOpen={false}>
            <div className="rrp__rewrites-section">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {bullet_reviews.filter(br => br.rewrite).map((br, i) => (
                  <div className="rw-compact" key={i}>
                    <span className="rw-compact__label">{br.source_label}</span>
                    <div className="rw-compact__row">
                      <span className="rw-compact__tag rw-compact__tag--before">Before</span>
                      <span className="rw-compact__text rw-compact__text--before">{br.original}</span>
                    </div>
                    <div className="rw-compact__row">
                      <span className="rw-compact__tag rw-compact__tag--after">After</span>
                      <span className="rw-compact__text rw-compact__text--after">{br.rewrite}</span>
                    </div>
                    {br.rewrite_rationale && (
                      <details className="rw-compact__why">
                        <summary>Why</summary>
                        <p>{br.rewrite_rationale}</p>
                      </details>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}
