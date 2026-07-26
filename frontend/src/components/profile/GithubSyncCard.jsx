import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncGithub } from '../../api/profile'
import './ProfileIngestion.css'

function GithubSyncCard({ result, onSuccess }) {
  const { token, user } = useAuth()
  const [username, setUsername] = useState(user?.github_username || '')
  const [pat, setPat] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')

  async function handleSync(e) {
    e.preventDefault()
    if (!username.trim()) {
      setError('Enter your GitHub username.')
      return
    }
    setSyncing(true)
    setError('')
    try {
      const data = await syncGithub(token, { username: username.trim(), githubToken: pat.trim() || undefined })
      setPat('')
      onSuccess(data)
    } catch (err) {
      setError(err.message || 'GitHub sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className={`ingest-card ${result ? 'ingest-card--done' : ''}`}>
      <div className="ingest-card__header">
        <h3>GitHub</h3>
        {result && <span className="ingest-card__badge">✓ Synced</span>}
      </div>

      {error && <p className="ingest-card__error">{error}</p>}

      <form className="ingest-card__manual-form" onSubmit={handleSync}>
        <label>
          GitHub username
          <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="octocat" />
        </label>
        <label>
          Personal access token {result && '(leave blank to reuse saved token)'}
          <input type="password" value={pat} onChange={(e) => setPat(e.target.value)} placeholder="ghp_..." />
        </label>
        <button type="submit" className="ingest-card__action" disabled={syncing}>
          {syncing ? 'Syncing…' : result ? 'Re-sync' : 'Connect & Sync'}
        </button>
      </form>

      {result && (
        <div className="ingest-card__stats">
          <span>{result.summary.repos_synced} repos</span>
          <span>{result.summary.languages_detected.length} languages</span>
          <span>{result.summary.total_commits_last_30_days} commits (30d)</span>
        </div>
      )}
    </div>
  )
}

export default GithubSyncCard