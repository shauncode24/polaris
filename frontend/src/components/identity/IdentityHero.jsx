// frontend/src/components/identity/IdentityHero.jsx
import './IdentityHero.css'

const SOURCE_CHECKLIST = [
  { key: 'resume', label: 'Resume' },
  { key: 'github', label: 'GitHub' },
  { key: 'leetcode', label: 'LeetCode' },
  { key: 'claim_audit', label: 'Projects' },
  { key: 'job_descriptions', label: 'Job Matches' },
]

function relativeTime(dateStr) {
  if (!dateStr) return null
  const then = new Date(dateStr).getTime()
  const diffMs = Date.now() - then
  const mins = Math.round(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.round(hours / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function confidenceTone(pct) {
  if (pct >= 75) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

// Redesigned per the "executive summary, not another dashboard" review:
// replaces the old "Triggered by X" line with a relative-time stamp,
// adds an "Identity confidence" badge derived from the already-computed
// evidence_coverage.completeness_score, and a compact source checklist
// built from source_freshness — all data that was already being
// returned by /identity, just never surfaced here before.
function IdentityHero({
  narrative,
  generatedAt,
  degraded,
  sourceEvent,
  isInvalidated,
  invalidatedReason,
  invalidatedAt,
  sourceFreshness,
  evidenceCoverage,
  onRefresh,
  refreshing,
}) {
  const rel = relativeTime(generatedAt)
  const fullDate = generatedAt ? new Date(generatedAt).toLocaleString() : null

  const confidencePct = evidenceCoverage ? Math.round((evidenceCoverage.completeness_score || 0) * 100) : null
  const tone = confidencePct != null ? confidenceTone(confidencePct) : 'weak'

  return (
    <div className="identity-hero">
      <div className="identity-hero__top">
        <div className="identity-hero__intro">
          <p className="identity-hero__eyebrow">Your reconciled engineering identity</p>
          <h1 className="identity-hero__headline">{narrative?.headline || 'Not enough data yet'}</h1>
          {rel && (
            <p
              className="identity-hero__meta"
              title={fullDate ? `${fullDate}${sourceEvent ? ` · ${sourceEvent}` : ''}` : undefined}
            >
              Updated {rel}
            </p>
          )}
        </div>

        <div className="identity-hero__actions">
          {confidencePct != null && (
            <div
              className={`identity-hero__confidence identity-hero__confidence--${tone}`}
              title={evidenceCoverage?.completeness_label}
            >
              <span className="identity-hero__confidence-pct">{confidencePct}%</span>
              <span className="identity-hero__confidence-label">Identity confidence</span>
            </div>
          )}
          <button type="button" className="identity-hero__btn" onClick={onRefresh} disabled={refreshing}>
            {refreshing ? 'Synthesizing…' : 'Refresh Identity'}
          </button>
        </div>
      </div>

      {narrative?.summary && <p className="identity-hero__summary">{narrative.summary}</p>}

      {sourceFreshness && Object.keys(sourceFreshness).length > 0 && (
        <div className="identity-hero__sources">
          {SOURCE_CHECKLIST.map(({ key, label }) => {
            const info = sourceFreshness[key]
            const connected = info?.connected
            return (
              <span
                key={key}
                className={`identity-hero__source ${connected ? 'identity-hero__source--on' : 'identity-hero__source--off'}`}
              >
                {connected ? '✓' : '·'} {label}
              </span>
            )
          })}
        </div>
      )}

      {degraded && (
        <p className="identity-hero__degraded">
          This synthesis used a simplified fallback — the underlying facts are still complete.
        </p>
      )}

      {isInvalidated && (
        <p className="identity-hero__invalidated">
          This snapshot was flagged as known-bad{invalidatedReason ? `: ${invalidatedReason}` : ''}
          {invalidatedAt ? ` (on ${new Date(invalidatedAt).toLocaleDateString()})` : ''}.
        </p>
      )}
    </div>
  )
}

export default IdentityHero