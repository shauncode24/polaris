import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncLeetcode, submitLeetcodeManual } from '../../api/profile'
import { IconCode } from '../icons/Icons'
import { IconRefresh } from '../icons/OnboardingIcons'
import Card from '../common/Card'
import './ProfileSectionCard.css'

function LeetCodeSyncCard({ result, onSuccess }) {
  const { token, user } = useAuth()
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')

  const username = result?.username || user?.leetcode_username || ''
  const totalSolved = result?.summary?.total_solved ?? 0
  const topics = (result?.insights?.topic_mastery || [])
    .filter((t) => t.problems > 0)
    .slice(0, 5)

  async function handleResync() {
    if (!username) return
    setSyncing(true)
    setError('')
    try {
      const data = await syncLeetcode(token, { username })
      if (data.status === 'degraded') {
        setError(data.reason || 'LeetCode sync degraded — try entering counts manually.')
      } else {
        onSuccess({ ...data, username })
      }
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
          <span className="psc__icon"><IconCode size={16} /></span>
          <h3 className="psc__title">LeetCode sync</h3>
        </div>
        {result && (
          <span className="psc__badge psc__badge--connected">Connected</span>
        )}
      </div>

      {error && <p className="psc__error">{error}</p>}

      {!result ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No LeetCode account connected.</span>
          <a href="/build-profile" className="psc__empty-cta">Connect LeetCode →</a>
        </div>
      ) : (
        <div className="psc__sync-body">
          <div className="psc__sync-username">{username}</div>
          <div className="psc__sync-sub">
            {totalSolved} problems solved · Synced recently
          </div>

          <div className="psc__pills">
            {topics.map((t) => (
              <span key={t.topic} className="psc__pill">{t.topic}</span>
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
              Enter counts manually
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

export default LeetCodeSyncCard
