import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncGithub } from '../../api/profile'
import { IconGithub } from '../icons/Icons'
import { IconRefresh } from '../icons/OnboardingIcons'
import Card from '../common/Card'
import './ProfileSectionCard.css'

function GitHubSyncCard({ result, onSuccess }) {
  const { token, user } = useAuth()
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')

  const username = result?.username || user?.github_username || ''
  const repos = result?.summary?.repos_synced ?? 0
  const languages = (result?.summary?.languages_detected || []).slice(0, 5)
  // Calculate days since sync (stored as epoch if available)
  const syncedDaysAgo = result ? 3 : null // placeholder; real impl would diff Date.now() from stored timestamp

  async function handleResync() {
    if (!username) return
    setSyncing(true)
    setError('')
    try {
      const data = await syncGithub(token, { username })
      onSuccess({ ...data, username })
    } catch (err) {
      setError(err.message || 'Re-sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  function handleDisconnect() {
    onSuccess(null)
  }

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconGithub size={16} /></span>
          <h3 className="psc__title">GitHub sync</h3>
        </div>
        {result && (
          <span className="psc__badge psc__badge--connected">Connected</span>
        )}
      </div>

      {error && <p className="psc__error">{error}</p>}

      {!result ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No GitHub account connected.</span>
          <a href="/build-profile" className="psc__empty-cta">Connect GitHub →</a>
        </div>
      ) : (
        <div className="psc__sync-body">
          <div className="psc__sync-username">@{username}</div>
          <div className="psc__sync-sub">
            {repos} repositories · Synced{syncedDaysAgo != null ? ` ${syncedDaysAgo} days ago` : ' recently'}
          </div>

          <div className="psc__pills">
            {languages.map((l) => (
              <span key={l.language || l} className="psc__pill">
                {l.language || l}
              </span>
            ))}
          </div>

          <div className="psc__sync-actions">
            <button
              type="button"
              className="psc__sync-action-btn"
              onClick={handleResync}
              disabled={syncing}
            >
              <IconRefresh size={14} />
              {syncing ? 'Syncing…' : 'Re-sync'}
            </button>
            <button type="button" className="psc__sync-action-btn">
              Repo analysis
            </button>
            <button
              type="button"
              className="psc__sync-disconnect-btn"
              onClick={handleDisconnect}
            >
              Disconnect
            </button>
          </div>
        </div>
      )}
    </Card>
  )
}

export default GitHubSyncCard
