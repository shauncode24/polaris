// frontend/src/components/leetcode/LeetCodeHeader.jsx
import { formatRelativeTime } from '../../utils/leetcodeMastery'
import './LeetCodeHeader.css'

export default function LeetCodeHeader({
  username,
  syncedAt,
  connected,
  onSync,
  onManualEntry,
  onDisconnect,
  syncing,
  totalSolved,
  contestRating,
}) {
  const relTime = formatRelativeTime(syncedAt)

  return (
    <div className="lc-header">
      <div className="lc-header__left">
        <div className="lc-header__meta" style={{ paddingLeft: 0 }}>
          <div className="lc-header__title-row">
            <span className="lc-header__username">{username || 'Not connected'}</span>
            {connected && (
              <span className="lc-header__badge">
                <span className="lc-header__badge-dot" /> Connected
              </span>
            )}
          </div>
          <div className="lc-header__sub">
            {connected ? (
              <>
                <span>Interview-readiness evidence</span>
                {relTime && (
                  <>
                    <span className="lc-header__sep" />
                    <span>last synced {relTime}</span>
                  </>
                )}
              </>
            ) : (
              <span>Connect your LeetCode profile to turn problem-solving history into interview-readiness evidence.</span>
            )}
          </div>
        </div>

        {connected && totalSolved != null && (
          <>
            <div className="lc-header__divider" />
            <div className="lc-header__stats-strip">
              <div className="lc-header__stat-item lc-header__stat-item--primary">
                <span className="lc-header__stat-val">{totalSolved}</span>
                <span className="lc-header__stat-lbl">TOTAL SOLVED</span>
              </div>
              {contestRating != null && (
                <div className="lc-header__stat-item">
                  <span className="lc-header__stat-val">{Math.round(contestRating)}</span>
                  <span className="lc-header__stat-lbl">CONTEST RATING</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="lc-header__right">
        <button type="button" className="lc-header__btn" onClick={onSync} disabled={syncing}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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