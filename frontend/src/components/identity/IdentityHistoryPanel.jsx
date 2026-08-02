// frontend/src/components/identity/IdentityHistoryPanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './IdentityHistoryPanel.css'

// Surfaces GET /identity/history, which was never called by the
// frontend at all — every past Engineering Identity snapshot
// (source_event, generated_at, degraded/invalidated flags, and the
// headline it produced) was previously invisible.
function IdentityHistoryPanel({ history = [] }) {
  if (history.length === 0) return null

  return (
    <CollapsibleSection title="Identity Snapshot History" defaultOpen={false}>
      <ul className="identity-history__list">
        {history.map((snap, i) => (
          <li
            key={i}
            className={`identity-history__item ${snap.is_invalidated ? 'identity-history__item--invalidated' : ''}`}
          >
            <div className="identity-history__row">
              <span className="identity-history__event">{snap.source_event}</span>
              <span className="identity-history__time">
                {snap.generated_at ? new Date(snap.generated_at).toLocaleString() : ''}
              </span>
              {snap.analysis_degraded && <span className="identity-history__flag">degraded</span>}
              {snap.is_invalidated && <span className="identity-history__flag identity-history__flag--bad">invalidated</span>}
            </div>
            {snap.narrative?.headline && <p className="identity-history__headline">{snap.narrative.headline}</p>}
            {snap.is_invalidated && snap.invalidated_reason && (
              <p className="identity-history__reason">Reason: {snap.invalidated_reason}</p>
            )}
          </li>
        ))}
      </ul>
    </CollapsibleSection>
  )
}

export default IdentityHistoryPanel