// frontend/src/components/identity/IdentityHistoryPanel.jsx
import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './IdentityHistoryPanel.css'

const VISIBLE_DEFAULT = 3

// Trimmed from an always-fully-rendered audit log to the last 3
// snapshots by default — this is developer-grade detail most users
// never need; "Show all" still gets there for anyone who does.
function IdentityHistoryPanel({ history = [] }) {
  const [showAll, setShowAll] = useState(false)

  if (history.length === 0) return null

  const visible = showAll ? history : history.slice(0, VISIBLE_DEFAULT)

  return (
    <CollapsibleSection title="Identity History" defaultOpen={false} subtitle={`Last ${visible.length} of ${history.length}`}>
      <ul className="identity-history__list">
        {visible.map((snap, i) => (
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

      {history.length > VISIBLE_DEFAULT && (
        <button type="button" className="identity-history__toggle" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show less' : `Show all ${history.length}`}
        </button>
      )}
    </CollapsibleSection>
  )
}

export default IdentityHistoryPanel