import { IconGithub } from '../icons/Icons'
import Button from '../common/Button'
import { formatRelativeTime } from '../../utils/formatRelativeTime'
import './GitHubHeader.css'

function GitHubHeader({ username, repoCount, syncedAt, connected, syncing, onSync, onAnalyze }) {
  return (
    <div className="gh-header">
      <div className="gh-header__left">
        <div className="gh-header__title-row">
          <h1>GitHub</h1>
          {connected && (
            <span className="gh-header__badge">
              <span className="gh-header__badge-dot" /> Connected
            </span>
          )}
        </div>
        <p className="gh-header__meta">
          {username ? `@${username}` : 'Not connected'}
          {connected && (
            <>
              <span className="gh-header__dot" />
              {repoCount} repositor{repoCount === 1 ? 'y' : 'ies'}
              <span className="gh-header__dot" />
              last synced {formatRelativeTime(syncedAt)}
            </>
          )}
        </p>
      </div>

      {connected && (
        <div className="gh-header__actions">
          <Button variant="outline" onClick={onSync} disabled={syncing}>
            {syncing ? 'Syncing…' : '↻ Sync now'}
          </Button>
          <Button variant="primary" onClick={onAnalyze} disabled={syncing} icon={<IconGithub size={15} />}>
            {syncing ? 'Analyzing…' : 'Analyze repositories'}
          </Button>
        </div>
      )}
    </div>
  )
}

export default GitHubHeader