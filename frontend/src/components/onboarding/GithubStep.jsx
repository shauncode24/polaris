import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { syncGithub } from '../../api/profile'
import { IconGithub } from '../icons/Icons'
import SimulatedProgressList from './SimulatedProgressList'
import StepFooterNav from './StepFooterNav'
import './onboarding-shared.css'

const PIPELINE_STEPS = ['Fetching repositories', 'Detecting languages', 'Reading commit history', 'Scoring projects']

function topProjectName(repositories = []) {
  if (repositories.length === 0) return '—'
  return [...repositories].sort((a, b) => (b.project_score?.overall || 0) - (a.project_score?.overall || 0))[0].name
}

function GithubStep({ result, onSuccess, onContinue, onSkip }) {
  const { token, user } = useAuth()
  const [username, setUsername] = useState(user?.github_username || '')
  const [pat, setPat] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')

  async function handleSync() {
    if (!username.trim()) { setError('Enter your GitHub username.'); return }
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
    <div>
      <p className="onb-eyebrow">Step 2 of 6 · GitHub</p>
      <h1 className="onb-title">Connect your GitHub</h1>
      <p className="onb-lead">
        Strongly recommended — it turns claimed skills into real evidence with project scoring
        and an activity signal. Your target-role matching gets noticeably sharper.
      </p>

      {error && <p className="onb-error">{error}</p>}

      <div className="onb-card">
        {!result && !syncing && (
          <>
            <div className="onb-field">
              <label>GitHub username</label>
              <input className="onb-input" placeholder="octocat" value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="onb-field">
              <label>Personal access token</label>
              <input className="onb-input" type="password" placeholder="ghp_…" value={pat} onChange={(e) => setPat(e.target.value)} />
              <span className="onb-hint">Read-only access. We never store write permissions.</span>
              <a
                className="onb-link-btn"
                href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens"
                target="_blank" rel="noreferrer"
              >
                ? How to generate a GitHub token
              </a>
            </div>
          </>
        )}

        {syncing && <SimulatedProgressList title={`Syncing @${username}`} steps={PIPELINE_STEPS} running={syncing} />}

        {result && !syncing && (
          <>
            <div className="onb-badge onb-badge--success" style={{ marginBottom: 10, display: 'inline-block' }}>Synced</div>
            <span style={{ marginLeft: 8, fontWeight: 600, color: 'var(--ink)' }}>@{result.user_id ? username : username}</span>
            <div className="onb-stat-grid">
              <div className="onb-stat-box">
                <div className="onb-stat-box__label">Repositories</div>
                <div className="onb-stat-box__value">{result.summary.repos_synced}</div>
              </div>
              <div className="onb-stat-box">
                <div className="onb-stat-box__label">Languages</div>
                <div className="onb-stat-box__value">{result.summary.languages_detected.length}</div>
              </div>
              <div className="onb-stat-box">
                <div className="onb-stat-box__label">Top project</div>
                <div className="onb-stat-box__value" style={{ fontSize: 14 }}>{topProjectName(result.repositories)}</div>
              </div>
            </div>
            <div className="onb-pill-row">
              {result.summary.languages_detected.slice(0, 4).map((l) => (
                <span key={l.language} className="onb-pill">{l.language}</span>
              ))}
            </div>
            <button type="button" className="onb-link-btn" style={{ marginTop: 14 }} onClick={() => onSuccess(null)}>
              ↻ Re-sync with a different account
            </button>
          </>
        )}
      </div>

      <StepFooterNav
        onSkip={onSkip}
        loading={syncing}
        continueLabel={result ? 'Continue' : 'Connect & sync'}
        onContinue={result ? onContinue : handleSync}
      />
    </div>
  )
}

export default GithubStep