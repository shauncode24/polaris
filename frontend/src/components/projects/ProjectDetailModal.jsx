import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import {
  getProjectClaimAudit,
  getProjectIntelligence,
  getProjectInterviewQuestions,
  getLinkOptions,
  confirmProjectLink,
} from '../../api/projects'
import InterviewToolkitPanel from './InterviewToolkitPanel'
import './ProjectDetailModal.css'

const RISK_LABEL = { high: 'High risk', medium: 'Medium risk', low: 'Low risk' }
const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }

function ClaimAuditSection({ project, token }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(regenerate = false) {
    setLoading(true)
    setError('')
    try {
      const data = await getProjectClaimAudit(token, project.id, regenerate)
      setReport(data)
    } catch (err) {
      setError(err.message || 'Could not load claim audit.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id])

  if (loading) return <p className="pdm__loading">Checking resume claims against verified GitHub evidence…</p>
  if (error) return <p className="pdm__error">{error}</p>
  if (!report) return null

  const { facts, narrative } = report

  return (
    <div className="pdm__section">
      <div className="pdm__section-header">
        <h3>Claim Audit</h3>
        <span className={`pdm__risk-badge pdm__risk-badge--${narrative.risk_level}`}>
          {RISK_LABEL[narrative.risk_level] || narrative.risk_level}
        </span>
      </div>
      <p className="pdm__headline">{narrative.headline}</p>

      {facts.architecture_flag && (
        <div className="pdm__architecture-flag-alert" style={{ fontSize: '12.5px', color: 'var(--danger)', background: 'var(--danger-soft)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', marginBottom: '10px' }}>
          <strong>Architecture mismatch:</strong> {facts.architecture_flag}
        </div>
      )}

      {facts.confirmed_claims?.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label pdm__subsection-label--success" style={{ color: 'var(--success)' }}>Verified claims</span>
          <ul>{facts.confirmed_claims.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}

      {facts.unsupported_claims.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label pdm__subsection-label--danger">Unsupported claims</span>
          <ul>{facts.unsupported_claims.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}

      {facts.undersold_work.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label pdm__subsection-label--info">Undersold — real, verified, not on your resume</span>
          <ul>{facts.undersold_work.map((c) => <li key={c}>{c}</li>)}</ul>
        </div>
      )}

      {facts.verified_facts && Object.keys(facts.verified_facts).length > 0 && (
        <div className="pdm__subsection pdm__subsection--verified-facts">
          <span className="pdm__subsection-label pdm__subsection-label--info">Verified GitHub evidence</span>
          <div className="pdm__verified-facts-grid">
            <div className="pdm__verified-fact-item">
              <strong>Quality Score</strong>
              <span>{facts.verified_facts.quality_score ?? 0}/100</span>
            </div>
            <div className="pdm__verified-fact-item">
              <strong>Activity Score</strong>
              <span>{facts.verified_facts.activity_score ?? 0}/100</span>
            </div>
            <div className="pdm__verified-fact-item">
              <strong>Architecture</strong>
              <span>{facts.verified_facts.architecture_depth || 'None'}</span>
            </div>
            <div className="pdm__verified-fact-item">
              <strong>Tests</strong>
              <span>{facts.verified_facts.has_tests ? 'Yes' : 'No'}</span>
            </div>
            <div className="pdm__verified-fact-item">
              <strong>CI/CD</strong>
              <span>{facts.verified_facts.has_ci ? 'Yes' : 'No'}</span>
            </div>
          </div>
          {(facts.verified_facts.technologies?.length > 0 || facts.verified_facts.capabilities?.length > 0) && (
            <div className="pdm__verified-facts-details">
              {facts.verified_facts.technologies?.length > 0 && (
                <p><strong>Verified Tech:</strong> {facts.verified_facts.technologies.join(', ')}</p>
              )}
              {facts.verified_facts.capabilities?.length > 0 && (
                <p><strong>Verified Capabilities:</strong> {facts.verified_facts.capabilities.join(', ')}</p>
              )}
            </div>
          )}
        </div>
      )}

      {narrative.talking_points.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label">Talking points</span>
          <ul>{narrative.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      {narrative.fixes.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label">Suggested fixes</span>
          <ul>{narrative.fixes.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}

      {report.analysis_degraded && (
        <div className="pdm__degraded" style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--warning)', marginTop: '8px', marginBottom: '8px' }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          Claim audit analysis degraded — showing deterministic fallback.
        </div>
      )}

      <button type="button" className="pdm__regenerate" onClick={() => load(true)}>Regenerate</button>
    </div>
  )
}

function IntelligenceSection({ project, token }) {
  const [framing, setFraming] = useState(
    'Explain this project in technical depth, as if I\'m interviewing at a top-tier tech company.'
  )
  const [comparisonTarget, setComparisonTarget] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function generate(regenerate = false) {
    setLoading(true)
    setError('')
    try {
      const data = await getProjectIntelligence(token, project.id, {
        framing, comparisonTarget: comparisonTarget || undefined, regenerate,
      })
      setReport(data)
    } catch (err) {
      setError(err.message || 'Could not generate this explanation.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pdm__section">
      <h3>Project Intelligence</h3>
      <p className="pdm__section-lead">Ask for a deep, framing-specific explanation or comparison — grounded only in verified facts.</p>

      <label className="pdm__field">
        <span>Framing</span>
        <textarea
          value={framing}
          onChange={(e) => setFraming(e.target.value)}
          rows={2}
        />
      </label>
      <label className="pdm__field">
        <span>Compare against (optional)</span>
        <input
          type="text"
          placeholder="e.g. Kong AI Gateway"
          value={comparisonTarget}
          onChange={(e) => setComparisonTarget(e.target.value)}
        />
      </label>

      <button type="button" className="pdm__generate" onClick={() => generate(false)} disabled={loading}>
        {loading ? 'Generating…' : 'Generate explanation'}
      </button>

      {error && <p className="pdm__error">{error}</p>}

      {report && (
        <div className="pdm__result">
          {report.insufficient_context ? (
            <p className="pdm__error">{report.context_note || 'Not enough data on this project to answer that.'}</p>
          ) : (
            <>
              {report.comparison_target && (
                <div className="pdm__comparison-target-heading" style={{ fontSize: '13px', fontWeight: '700', color: 'var(--ink)', background: 'var(--surface-soft)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', marginBottom: '8px' }}>
                  Comparing against: {report.comparison_target}
                </div>
              )}
              <p>{report.explanation}</p>
              {report.strongest_technical_decision && (
                <div className="pdm__subsection">
                  <span className="pdm__subsection-label">Strongest technical decision</span>
                  <p>{report.strongest_technical_decision}</p>
                </div>
              )}
              {report.weakest_point && (
                <div className="pdm__subsection">
                  <span className="pdm__subsection-label">Weakest point</span>
                  <p>{report.weakest_point}</p>
                </div>
              )}
              {report.comparison_notes && (
                <div className="pdm__subsection">
                  <span className="pdm__subsection-label">Comparison notes</span>
                  <p>{report.comparison_notes}</p>
                </div>
              )}
              {report.analysis_degraded && (
                <div className="pdm__degraded" style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--warning)', marginTop: '8px' }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  Intelligence analysis degraded — showing deterministic fallback.
                </div>
              )}
              <div className="pdm__footer-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
                <button type="button" className="pdm__regenerate" onClick={() => generate(true)}>Regenerate</button>
                {report.generated_at && (
                  <span className="pdm__generated-at" style={{ fontSize: '11.5px', color: 'var(--text-soft)' }}>Generated {new Date(report.generated_at).toLocaleDateString()}</span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function InterviewQuestionsSection({ project, token }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function load(regenerate = false) {
    setLoading(true)
    setError('')
    try {
      const data = await getProjectInterviewQuestions(token, project.id, regenerate)
      setReport(data)
    } catch (err) {
      setError(err.message || 'Could not generate interview questions.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="pdm__section">
      <h3>Grounded Interview Questions</h3>
      {!report && (
        <button type="button" className="pdm__generate" onClick={() => load(false)} disabled={loading}>
          {loading ? 'Generating…' : 'Generate questions'}
        </button>
      )}
      {error && <p className="pdm__error">{error}</p>}
      {report && (
        <>
          <ul className="pdm__questions">
            {report.questions.map((q, i) => (
              <li key={i}>
                <span className={`pdm__difficulty pdm__difficulty--${q.difficulty}`}>
                  {DIFFICULTY_LABEL[q.difficulty] || q.difficulty}
                </span>
                <div>
                  <p className="pdm__question-text">{q.question}</p>
                  {q.grounded_in && <p className="pdm__grounded-in">Grounded in: {q.grounded_in}</p>}
                </div>
              </li>
            ))}
          </ul>
          {report.analysis_degraded && (
            <div className="pdm__degraded" style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px', color: 'var(--warning)', marginTop: '8px', marginBottom: '8px' }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              Interview questions analysis degraded — showing deterministic fallback.
            </div>
          )}
          <div className="pdm__footer-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '12px' }}>
            <button type="button" className="pdm__regenerate" onClick={() => load(true)}>Regenerate</button>
            {report.generated_at && (
              <span className="pdm__generated-at" style={{ fontSize: '11.5px', color: 'var(--text-soft)' }}>Generated {new Date(report.generated_at).toLocaleDateString()}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function ProjectDetailModal({ project, onClose, onLinkConfirmed }) {
  const { token } = useAuth()
  const [currentProject, setCurrentProject] = useState(project)
  const [availableRepos, setAvailableRepos] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [linking, setLinking] = useState(false)
  const [linkError, setLinkError] = useState('')

  useEffect(() => {
    setCurrentProject(project)
  }, [project])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  useEffect(() => {
    if (currentProject && !currentProject.has_repo) {
      getLinkOptions(token)
        .then((data) => setAvailableRepos(data.repositories || []))
        .catch((err) => console.error('Failed to load repo options:', err))
    }
  }, [currentProject, token])

  async function handleLinkProject() {
    if (!selectedRepo) return
    setLinking(true)
    setLinkError('')
    try {
      await confirmProjectLink(token, currentProject.id, selectedRepo)
      setCurrentProject((prev) => ({ ...prev, has_repo: true, matched_repo_name: selectedRepo }))
      onLinkConfirmed?.()
    } catch (err) {
      setLinkError(err.message || 'Failed to connect repository.')
    } finally {
      setLinking(false)
    }
  }

  if (!currentProject) return null

  return (
    <>
      {/* Backdrop is deliberately light and click-through-free only for closing,
          not for dimming the list — the portfolio behind it stays legible. */}
      <div className="pdm__scrim" onClick={onClose} />
      <aside className="pdm__panel" role="dialog" aria-label={`${currentProject.name} details`}>
        <div className="pdm__header">
          <div>
            <h2>{currentProject.name}</h2>
            <p className="pdm__tagline">{currentProject.tagline}</p>
          </div>
          <button type="button" className="pdm__close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="pdm__scroll">
          {!currentProject.has_repo && (
            <div className="pdm__link-container">
              <p className="pdm__notice">
                No matched GitHub repository — claim audit and verified facts aren't available until this
                project is linked to a synced repo.
              </p>
              <div className="pdm__link-selector">
                <label htmlFor="repo-select">Connect to a GitHub repository:</label>
                <div className="pdm__link-row">
                  <select
                    id="repo-select"
                    value={selectedRepo}
                    onChange={(e) => setSelectedRepo(e.target.value)}
                    disabled={linking}
                  >
                    <option value="">-- Select a repository --</option>
                    {availableRepos.map((repo) => (
                      <option key={repo} value={repo}>{repo}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={handleLinkProject}
                    disabled={linking || !selectedRepo}
                    className="pdm__link-button"
                  >
                    {linking ? 'Linking...' : 'Connect'}
                  </button>
                </div>
                {linkError && <p className="pdm__link-error">{linkError}</p>}
              </div>
            </div>
          )}

          <div className="pdm__body">
            {currentProject.has_repo && <ClaimAuditSection project={currentProject} token={token} />}
            <IntelligenceSection project={currentProject} token={token} />
            <div className="pdm__section">
              <h3>Interview Toolkit</h3>
              <InterviewToolkitPanel featuredProjectName={currentProject.name} />
            </div>
            <InterviewQuestionsSection project={currentProject} token={token} />
          </div>
        </div>
      </aside>
    </>
  )
}

export default ProjectDetailModal