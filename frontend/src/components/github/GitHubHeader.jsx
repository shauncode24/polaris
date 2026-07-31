import { IconGithub } from '../icons/Icons'
import Button from '../common/Button'
import { formatRelativeTime } from '../../utils/formatRelativeTime'
import './GitHubHeader.css'

export default function GitHubHeader({
  username,
  repoCount,
  syncedAt,
  connected,
  syncing,
  onSync,
  onAnalyze,
  avgScore,
  commits30d,
}) {
  const relTime = formatRelativeTime(syncedAt)

  function getScoreTone(score) {
    if (score == null) return ''
    if (score >= 75) return 'strong'
    if (score >= 50) return 'partial'
    return 'weak'
  }

  return (
    <div className="gh-header">
      <div className="gh-header__left">
        <div className="gh-header__meta" style={{ paddingLeft: 0 }}>
          <div className="gh-header__title-row">
            <span className="gh-header__username">{username ? `@${username}` : 'Not connected'}</span>
            {connected && (
              <span className="gh-header__badge">
                <span className="gh-header__badge-dot" /> Connected
              </span>
            )}
          </div>
          <div className="gh-header__sub">
            {connected ? (
              <>
                <span>{repoCount} repository{repoCount === 1 ? '' : 'ies'}</span>
                <span className="gh-header__sep" />
                {relTime && <span>last synced {relTime}</span>}
              </>
            ) : (
              <span>Connect your GitHub profile to analyze your repositories</span>
            )}
          </div>
        </div>

        {connected && avgScore !== undefined && (
          <>
            <div className="gh-header__divider" />
            <div className="gh-header__stats-strip">
              <div className={`gh-header__stat-item gh-header__stat-item--primary tone-${getScoreTone(avgScore)}`}>
                <span className="gh-header__stat-val">{avgScore ?? '—'}</span>
                <span className="gh-header__stat-lbl">AVG REPO SCORE</span>
              </div>
              {commits30d !== undefined && (
                <div className="gh-header__stat-item">
                  <span className="gh-header__stat-val">{commits30d}</span>
                  <span className="gh-header__stat-lbl">30D COMMITS</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {connected && (
        <div className="gh-header__right">
          <button
            type="button"
            className="gh-header__btn"
            onClick={onSync}
            disabled={syncing}
          >
            {syncing ? 'Syncing…' : '↻ Sync now'}
          </button>
          <button
            type="button"
            className="gh-header__btn gh-header__btn--primary"
            onClick={onAnalyze}
            disabled={syncing}
          >
            <IconGithub size={13} style={{ marginRight: 6 }} />
            {syncing ? 'Analyzing…' : 'Analyze repositories'}
          </button>
        </div>
      )}
    </div>
  )
}