// frontend/src/components/leetcode/LeetCodeHeader.jsx
import { formatRelativeTime } from '../../utils/leetcodeMastery'
import './LeetCodeHeader.css'

function LeetCodeHeader({ username, syncedAt, connected, onSync, onManualEntry, onDisconnect, syncing }) {
  const relTime = formatRelativeTime(syncedAt)

  return (
    <div className="lc-header">
      <div className="lc-header__left">
        <div className="lc-header__title-row">
          <h1>LeetCode</h1>
          {connected && (
            <span className="lc-header__status">
              <span className="lc-header__status-dot" /> Connected
            </span>
          )}
        </div>
        <p className="lc-header__sub">
          {connected ? (
            <>
              {username}
              {relTime && <> · last synced {relTime}</>}
              <> · interview-readiness evidence</>
            </>
          ) : (
            'Connect your LeetCode profile to turn problem-solving history into interview-readiness evidence.'
          )}
        </p>
      </div>

      <div className="lc-header__actions">
        <button type="button" className="lc-header__btn" onClick={onSync} disabled={syncing}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 11a8 8 0 1 0-2.2 5.7" /><path d="M20 5v6h-6" />
          </svg>
          {syncing ? 'Syncing…' : 'Sync now'}
        </button>
        <button type="button" className="lc-header__btn" onClick={onManualEntry}>
          Manual entry
        </button>
        {connected && (
          <button type="button" className="lc-header__btn lc-header__btn--danger" onClick={onDisconnect}>
            Disconnect
          </button>
        )}
      </div>
    </div>
  )
}

export default LeetCodeHeader