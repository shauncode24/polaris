import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncLeetcode, submitLeetcodeManual } from '../../api/profile'
import SimulatedProgressList from './SimulatedProgressList'
import StepFooterNav from './StepFooterNav'
import './onboarding-shared.css'

const PIPELINE_STEPS = ['Looking up public profile', 'Reading solved problems', 'Grouping by topic']

function parseTagLine(line) {
  const [tag, count] = line.split(':').map((s) => s.trim())
  return tag && count && !Number.isNaN(Number(count)) ? [tag, Number(count)] : null
}

function LeetCodeStep({ result, onSuccess, onContinue, onSkip }) {
  const { token, user } = useAuth()
  const [username, setUsername] = useState(user?.leetcode_username || '')
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [showManualForm, setShowManualForm] = useState(false)
  const [manualText, setManualText] = useState('')

  async function handleSync() {
    if (!username.trim()) { setError('Enter your LeetCode username.'); return }
    setSyncing(true)
    setError('')
    try {
      const data = await syncLeetcode(token, { username: username.trim() })
      if (data.status === 'degraded' && data.fallback_form_required) {
        setShowManualForm(true)
        setError(data.reason || 'LeetCode sync is temporarily unavailable — enter your counts manually below.')
      } else {
        onSuccess(data)
      }
    } catch (err) {
      setError(err.message || 'LeetCode sync failed.')
      setShowManualForm(true)
    } finally {
      setSyncing(false)
    }
  }

  async function handleManualSubmit() {
    const tagCounts = {}
    for (const line of manualText.split('\n')) {
      if (!line.trim()) continue
      const parsed = parseTagLine(line)
      if (!parsed) { setError(`Couldn't parse "${line}" — use "tag-slug: count".`); return }
      tagCounts[parsed[0]] = parsed[1]
    }
    if (Object.keys(tagCounts).length === 0) { setError('Add at least one line, e.g. "dynamic-programming: 42".'); return }
    try {
      const data = await submitLeetcodeManual(token, tagCounts)
      onSuccess(data)
      setShowManualForm(false)
      setError('')
    } catch (err) {
      setError(err.message || 'Could not save your manual submission.')
    }
  }

  const topics = (result?.insights?.topic_mastery || []).filter((t) => t.problems > 0).slice(0, 5)

  return (
    <div>
      <p className="onb-eyebrow">Step 3 of 6 · LeetCode</p>
      <h1 className="onb-title">Add your LeetCode signal</h1>
      <p className="onb-lead">
        Optional. Your public profile shows problem-solving depth by topic — useful for interview prep
        recommendations. No login needed.
      </p>

      {error && <p className="onb-error">{error}</p>}

      <div className="onb-card">
        {!result && !syncing && !showManualForm && (
          <div className="onb-field">
            <label>LeetCode username</label>
            <input className="onb-input" placeholder="your-handle" value={username} onChange={(e) => setUsername(e.target.value)} />
            <span className="onb-hint">Uses your public profile — no password required.</span>
          </div>
        )}

        {showManualForm && !result && (
          <div className="onb-field">
            <label>Manual tag counts — one per line, as <code>tag-slug: count</code></label>
            <textarea
              className="onb-textarea" rows={5}
              placeholder={'dynamic-programming: 42\narray: 88'}
              value={manualText} onChange={(e) => setManualText(e.target.value)}
            />
          </div>
        )}

        {syncing && <SimulatedProgressList title={`Syncing ${username}`} steps={PIPELINE_STEPS} running={syncing} />}

        {result && !syncing && (
          <>
            <div className="onb-badge onb-badge--success" style={{ marginBottom: 10, display: 'inline-block' }}>Added</div>
            <span style={{ marginLeft: 8, fontWeight: 600, color: 'var(--ink)' }}>{username}</span>
            <div className="onb-stat-box" style={{ marginTop: 14 }}>
              <div className="onb-stat-box__value" style={{ fontSize: 30 }}>{result.summary?.total_solved ?? '—'}</div>
              <div className="onb-stat-box__label">problems solved</div>
            </div>
            {topics.length > 0 && (
              <>
                <p className="onb-hint" style={{ marginTop: 14 }}>Topics covered</p>
                <div className="onb-pill-row">
                  {topics.map((t) => <span key={t.topic} className="onb-pill">{t.topic}</span>)}
                </div>
              </>
            )}
          </>
        )}
      </div>

      <StepFooterNav
        onSkip={onSkip}
        loading={syncing}
        continueLabel={result ? 'Continue' : showManualForm ? 'Save manual counts' : 'Connect & sync'}
        onContinue={result ? onContinue : showManualForm ? handleManualSubmit : handleSync}
      />
    </div>
  )
}

export default LeetCodeStep