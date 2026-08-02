// frontend/src/components/identity/IdentityHero.jsx
import './IdentityHero.css'

const SOURCE_EVENT_LABELS = {
  manual_refresh: 'Manual refresh',
  'resume upload': 'Resume upload',
  'resume analysis': 'Resume analysis',
  'github sync': 'GitHub sync',
  'leetcode sync': 'LeetCode sync',
  'leetcode manual submission': 'LeetCode manual submission',
  'job description analysis': 'Job description analysis',
  'claim audit': 'Claim audit',
  'project link confirmed': 'Project link confirmed',
  'project link removed': 'Project link removed',
}

function IdentityHero({
  narrative,
  generatedAt,
  degraded,
  sourceEvent,
  isInvalidated,
  invalidatedReason,
  invalidatedAt,
  onRefresh,
  refreshing,
}) {
  const relTime = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="identity-hero">
      <div className="identity-hero__top">
        <div>
          <p className="identity-hero__eyebrow">Your reconciled engineering identity</p>
          <h1 className="identity-hero__headline">{narrative?.headline || 'Not enough data yet'}</h1>
          {(relTime || sourceEvent) && (
            <p className="identity-hero__meta">
              {relTime && <>Last synthesized {relTime}</>}
              {relTime && sourceEvent && <> · </>}
              {sourceEvent && <>Triggered by {SOURCE_EVENT_LABELS[sourceEvent] || sourceEvent}</>}
            </p>
          )}
        </div>
        <button type="button" className="identity-hero__btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Synthesizing…' : 'Refresh Identity'}
        </button>
      </div>

      {narrative?.summary && <p className="identity-hero__summary">{narrative.summary}</p>}

      {narrative?.freshness_note && (
        <p className="identity-hero__freshness">{narrative.freshness_note}</p>
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