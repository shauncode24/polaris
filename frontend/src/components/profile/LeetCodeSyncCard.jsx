import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncLeetcode, submitLeetcodeManual } from '../../api/profile'
import './ProfileIngestion.css'

function parseTagLine(line) {
  const [tag, count] = line.split(':').map((s) => s.trim())
  return tag && count && !Number.isNaN(Number(count)) ? [tag, Number(count)] : null
}

function LeetCodeSyncCard({ result, onSuccess }) {
  const { token, user } = useAuth()
  const [username, setUsername] = useState(user?.leetcode_username || '')
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualText, setManualText] = useState('')
  const [manualError, setManualError] = useState('')

  async function handleSync(e) {
    e.preventDefault()
    if (!username.trim()) {
      setError('Enter your LeetCode username.')
      return
    }
    setSyncing(true)
    setError('')
    try {
      const data = await syncLeetcode(token, { username: username.trim() })
      if (data.status === 'degraded' && data.fallback_form_required) {
        setShowManualForm(true)
        setError(data.reason || 'LeetCode sync is temporarily unavailable — enter your counts manually below.')
      } else {
        setShowManualForm(false)
        onSuccess(data)
      }
    } catch (err) {
      setError(err.message || 'LeetCode sync failed.')
      setShowManualForm(true)
    } finally {
      setSyncing(false)
    }
  }

  async function handleManualSubmit(e) {
    e.preventDefault()
    setManualError('')
    const tagCounts = {}
    for (const line of manualText.split('\n')) {
      if (!line.trim()) continue
      const parsed = parseTagLine(line)
      if (!parsed) {
        setManualError(`Couldn't parse "${line}" — use the format "tag-slug: count".`)
        return
      }
      tagCounts[parsed[0]] = parsed[1]
    }
    if (Object.keys(tagCounts).length === 0) {
      setManualError('Add at least one line, e.g. "dynamic-programming: 42".')
      return
    }
    try {
      const data = await submitLeetcodeManual(token, tagCounts)
      onSuccess(data)
      setShowManualForm(false)
      setError('')
    } catch (err) {
      setManualError(err.message || 'Could not save your manual submission.')
    }
  }

  return (
    <div className={`ingest-card ${result ? 'ingest-card--done' : ''}`}>
      <div className="ingest-card__header">
        <h3>LeetCode</h3>
        {result && <span className="ingest-card__badge">✓ Synced</span>}
      </div>

      {error && <p className="ingest-card__error">{error}</p>}

      {!showManualForm && (
        <form className="ingest-card__manual-form" onSubmit={handleSync}>
          <label>
            LeetCode username
            <input type="text" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="your-leetcode-handle" />
          </label>
          <button type="submit" className="ingest-card__action" disabled={syncing}>
            {syncing ? 'Syncing…' : result ? 'Re-sync' : 'Connect & Sync'}
          </button>
        </form>
      )}

      {result && !showManualForm && (
        <div className="ingest-card__stats">
          <span>{result.summary.total_solved != null ? `${result.summary.total_solved} problems` : `${result.tags.length} tags synced`}</span>
          <span>{result.tags.length} tags</span>
        </div>
      )}

      {showManualForm && (
        <form className="ingest-card__manual-form" onSubmit={handleManualSubmit}>
          <label>
            Manual tag counts — one per line, as <code>tag-slug: count</code>
            <textarea rows={5} value={manualText} onChange={(e) => setManualText(e.target.value)} placeholder={'dynamic-programming: 42\narray: 88'} />
          </label>
          {manualError && <p className="ingest-card__error">{manualError}</p>}
          <button type="submit" className="ingest-card__action">Save manual counts</button>
        </form>
      )}
    </div>
  )
}

export default LeetCodeSyncCard