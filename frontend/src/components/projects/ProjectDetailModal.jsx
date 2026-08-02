import { useEffect, useMemo, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import {
  getProjectClaimAudit,
  getProjectIntelligence,
  getProjectInterviewQuestions,
  getLinkOptions,
  confirmProjectLink,
  unlinkProject,
} from '../../api/projects'
import StarRating from './StarRating'
import './ProjectDetailModal.css'

const RISK_LABEL = { high: 'High risk', medium: 'Medium risk', low: 'Low risk' }
const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'analysis', label: 'Analysis' },
  { key: 'interview', label: 'Interview' },
  { key: 'improve', label: 'Improve' },
]

const FRAMING_CHIPS = [
  { key: 'explain_simply', label: 'Explain Simply', framing: "Explain this project in plain terms, like you're describing it to a non-technical person." },
  { key: 'technical_deep_dive', label: 'Technical Deep Dive', framing: 'Give me a technical deep dive, including the hardest engineering decision made.' },
  { key: 'architecture', label: 'Architecture Review', framing: "Walk me through the architecture — strengths, weaknesses, and what you'd improve given more time." },
  { key: 'behavioral', label: 'Behavioral Story', framing: 'What behavioral stories (ownership, conflict, failure) does this project let me tell?' },
  { key: 'system_design', label: 'System Design', framing: 'Turn this into a system design interview question and answer it the way it was built.' },
  { key: 'recruiter', label: 'Recruiter View', framing: 'What would a recruiter ask about this in a 20-second resume skim?' },
]

// Shared claim-audit fetch — Overview needs the verified-facts half,
// Analysis needs the claim-vs-implementation half. Fetching once here
// and passing the same report down keeps both tabs in agreement and
// avoids firing the same request twice when a user flips between them.
function useClaimAudit(project, token) {
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
    if (project.has_repo) load(false)
    else setLoading(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, project.has_repo])

  return { report, loading, error, reload: load }
}

function EngineeringScoreStrip({ verifiedFacts }) {
  if (!verifiedFacts) return null
  return (
    <div className="pdm__score-strip">
      <div className="pdm__score-item">
        <span className="pdm__score-label">Quality</span>
        <span className="pdm__score-value">{verifiedFacts.quality_score ?? 0}/100</span>
      </div>
      <div className="pdm__score-item">
        <span className="pdm__score-label">Activity</span>
        <span className="pdm__score-value">{verifiedFacts.activity_score ?? 0}/100</span>
      </div>
      <div className="pdm__score-item">
        <span className="pdm__score-label">Architecture</span>
        <span className="pdm__score-value">{verifiedFacts.architecture_depth || 'None'}</span>
      </div>
      <div className="pdm__score-item">
        <span className="pdm__score-label">Tests</span>
        <span className="pdm__score-value">{verifiedFacts.has_tests ? 'Yes' : 'No'}</span>
      </div>
      <div className="pdm__score-item">
        <span className="pdm__score-label">CI/CD</span>
        <span className="pdm__score-value">{verifiedFacts.has_ci ? 'Yes' : 'No'}</span>
      </div>
    </div>
  )
}

/* ───────────────────────── Tab 1 — Overview ───────────────────────── */
function OverviewTab({ project, claimAudit }) {
  const { report, loading } = claimAudit
  const verifiedFacts = report?.facts?.verified_facts

  return (
    <div className="pdm__tab-body">
      <div className="pdm__section">
        <span className="pdm__subsection-label">Summary</span>
        <p>{project.description || project.tagline || 'No description on file yet.'}</p>
      </div>

      {project.stack?.length > 0 && (
        <div className="pdm__section">
          <span className="pdm__subsection-label">Technologies</span>
          <div className="pdm__chip-row">
            {project.stack.map((t) => <span key={t} className="pdm__chip">{t}</span>)}
          </div>
        </div>
      )}

      {project.engineering_tags?.length > 0 && (
        <div className="pdm__section">
          <span className="pdm__subsection-label">Capabilities</span>
          <div className="pdm__chip-row">
            {project.engineering_tags.map((t) => <span key={t} className="pdm__chip pdm__chip--accent">{t}</span>)}
          </div>
        </div>
      )}

      {!project.has_repo && (
        <p className="pdm__notice">
          No matched GitHub repository yet — connect one from the Analysis tab to unlock verified evidence.
        </p>
      )}

      {project.has_repo && loading && <p className="pdm__loading">Loading verified evidence…</p>}

      {project.has_repo && verifiedFacts && (
        <div className="pdm__section">
          <span className="pdm__subsection-label">Verified Evidence Summary</span>
          <EngineeringScoreStrip verifiedFacts={verifiedFacts} />
          {(verifiedFacts.technologies?.length > 0 || verifiedFacts.capabilities?.length > 0) && (
            <div className="pdm__verified-facts-details">
              {verifiedFacts.technologies?.length > 0 && (
                <p><strong>Verified tech:</strong> {verifiedFacts.technologies.join(', ')}</p>
              )}
              {verifiedFacts.capabilities?.length > 0 && (
                <p><strong>Verified capabilities:</strong> {verifiedFacts.capabilities.join(', ')}</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Tab 2 — Analysis ───────────────────────── */
function LinkRepoPrompt({ project, token, onLinked }) {
  const [availableRepos, setAvailableRepos] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [linking, setLinking] = useState(false)
  const [linkError, setLinkError] = useState('')

  useEffect(() => {
    getLinkOptions(token)
      .then((data) => setAvailableRepos(data.repositories || []))
      .catch((err) => console.error('Failed to load repo options:', err))
  }, [token])

  async function handleLink() {
    if (!selectedRepo) return
    setLinking(true)
    setLinkError('')
    try {
      await confirmProjectLink(token, project.id, selectedRepo)
      onLinked?.(selectedRepo)
    } catch (err) {
      setLinkError(err.message || 'Failed to connect repository.')
    } finally {
      setLinking(false)
    }
  }

  return (
    <div className="pdm__link-container">
      <p className="pdm__notice">
        Claim audit and verified facts aren't available until this project is linked to a synced repo.
      </p>
      <div className="pdm__link-selector">
        <label htmlFor="repo-select">Connect to a GitHub repository:</label>
        <div className="pdm__link-row">
          <select id="repo-select" value={selectedRepo} onChange={(e) => setSelectedRepo(e.target.value)} disabled={linking}>
            <option value="">-- Select a repository --</option>
            {availableRepos.map((repo) => <option key={repo} value={repo}>{repo}</option>)}
          </select>
          <button type="button" onClick={handleLink} disabled={linking || !selectedRepo} className="pdm__link-button">
            {linking ? 'Linking...' : 'Connect'}
          </button>
        </div>
        {linkError && <p className="pdm__link-error">{linkError}</p>}
      </div>
    </div>
  )
}

function AnalysisTab({ project, token, claimAudit, onLinked, onUnlink }) {
  const { report, loading, error, reload } = claimAudit
  const [showChangeRepo, setShowChangeRepo] = useState(false)

  if (!project.has_repo || showChangeRepo) {
    return (
      <div className="pdm__tab-body">
        {project.has_repo && (
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12.5px', color: 'var(--text-soft)' }}>
              Currently connected: <strong>{project.matched_repo_name}</strong>
            </span>
            <button
              type="button"
              className="pdm__prompt-chip"
              style={{ fontSize: '11.5px', padding: '4px 10px' }}
              onClick={() => setShowChangeRepo(false)}
            >
              Cancel
            </button>
          </div>
        )}
        <LinkRepoPrompt
          project={project}
          token={token}
          onLinked={(repoName) => {
            setShowChangeRepo(false)
            onLinked?.(repoName)
          }}
        />
      </div>
    )
  }

  if (loading) return <div className="pdm__tab-body"><p className="pdm__loading">Checking resume claims against verified GitHub evidence…</p></div>
  if (error) return <div className="pdm__tab-body"><p className="pdm__error">{error}</p></div>
  if (!report) return null

  const { facts, narrative } = report

  return (
    <div className="pdm__tab-body">
      <div className="pdm__section-header">
        <span className={`pdm__risk-badge pdm__risk-badge--${narrative.risk_level}`}>
          {RISK_LABEL[narrative.risk_level] || narrative.risk_level}
        </span>
        <button type="button" className="pdm__regenerate" onClick={() => reload(true)}>Regenerate</button>
      </div>
      <p className="pdm__headline">{narrative.headline}</p>

      <EngineeringScoreStrip verifiedFacts={facts.verified_facts} />

      {facts.architecture_flag && (
        <div className="pdm__architecture-flag">
          <strong>Architecture mismatch:</strong> {facts.architecture_flag}
        </div>
      )}

      <div className="pdm__claim-groups">
        {facts.confirmed_claims?.length > 0 && (
          <div className="pdm__subsection">
            <span className="pdm__subsection-label pdm__subsection-label--success">Verified</span>
            <ul>{facts.confirmed_claims.map((c) => <li key={c}>✓ {c}</li>)}</ul>
          </div>
        )}
        {facts.unsupported_claims.length > 0 && (
          <div className="pdm__subsection">
            <span className="pdm__subsection-label pdm__subsection-label--danger">Unsupported</span>
            <ul>{facts.unsupported_claims.map((c) => <li key={c}>✗ {c}</li>)}</ul>
          </div>
        )}
        {facts.undersold_work.length > 0 && (
          <div className="pdm__subsection">
            <span className="pdm__subsection-label pdm__subsection-label--info">Undersold</span>
            <ul>{facts.undersold_work.map((c) => <li key={c}>+ {c}</li>)}</ul>
          </div>
        )}
      </div>

      {narrative.talking_points.length > 0 && (
        <div className="pdm__subsection">
          <span className="pdm__subsection-label">Talking points</span>
          <ul>{narrative.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
        </div>
      )}

      {report.analysis_degraded && (
        <div className="pdm__degraded">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
          Claim audit degraded — showing deterministic fallback.
        </div>
      )}

      <div style={{ borderTop: '1px solid var(--border)', paddingTop: '16px', marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-soft)', display: 'block', marginBottom: '4px' }}>
            Connected Repository
          </span>
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ink)' }}>
            {project.matched_repo_name}
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            className="pdm__regenerate"
            style={{ margin: 0 }}
            onClick={() => setShowChangeRepo(true)}
          >
            Change
          </button>
          <button
            type="button"
            className="pdm__regenerate"
            style={{ margin: 0, color: 'var(--danger)', borderColor: 'rgba(220, 38, 38, 0.2)' }}
            onClick={onUnlink}
          >
            Disconnect
          </button>
        </div>
      </div>
    </div>
  )
}

/* ───────────────────────── Tab 3 — Interview ───────────────────────── */
function IntelligenceBlock({ project, token }) {
  const [framing, setFraming] = useState(FRAMING_CHIPS[0].framing)
  const [activeChip, setActiveChip] = useState(FRAMING_CHIPS[0].key)
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

  function selectChip(chip) {
    setActiveChip(chip.key)
    setFraming(chip.framing)
  }

  return (
    <div className="pdm__section">
      <span className="pdm__subsection-label">Project Intelligence</span>
      <div className="pdm__chip-row pdm__chip-row--interactive">
        {FRAMING_CHIPS.map((chip) => (
          <button
            key={chip.key}
            type="button"
            className={`pdm__prompt-chip ${activeChip === chip.key ? 'pdm__prompt-chip--active' : ''}`}
            onClick={() => selectChip(chip)}
          >
            {chip.label}
          </button>
        ))}
        <button
          type="button"
          className={`pdm__prompt-chip ${activeChip === 'custom' ? 'pdm__prompt-chip--active' : ''}`}
          onClick={() => setActiveChip('custom')}
        >
          Custom Prompt
        </button>
      </div>

      {activeChip === 'custom' && (
        <textarea
          className="pdm__textarea"
          rows={2}
          value={framing}
          onChange={(e) => setFraming(e.target.value)}
          placeholder="Describe how you want this project framed…"
        />
      )}

      <input
        type="text"
        className="pdm__input"
        placeholder="Compare against (optional), e.g. Kong AI Gateway"
        value={comparisonTarget}
        onChange={(e) => setComparisonTarget(e.target.value)}
      />

      <button type="button" className="pdm__generate" onClick={() => generate(false)} disabled={loading}>
        {loading ? 'Generating…' : 'Generate'}
      </button>

      {error && <p className="pdm__error">{error}</p>}

      {report && (
        <div className="pdm__result">
          {report.insufficient_context ? (
            <p className="pdm__error">{report.context_note || 'Not enough data on this project to answer that.'}</p>
          ) : (
            <>
              {report.comparison_target && (
                <div className="pdm__comparison-heading">Comparing against: {report.comparison_target}</div>
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
              <div className="pdm__footer-row">
                <button type="button" className="pdm__regenerate" onClick={() => generate(true)}>Regenerate</button>
                {report.generated_at && (
                  <span className="pdm__generated-at">Generated {new Date(report.generated_at).toLocaleDateString()}</span>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

function InterviewQuestionsBlock({ project, token }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
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

  // Generate once automatically, display immediately — no extra click
  // to reveal what's already the whole point of this block.
  useEffect(() => {
    load(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id])

  return (
    <div className="pdm__section">
      <span className="pdm__subsection-label">Grounded Interview Questions</span>
      {loading && <p className="pdm__loading">Generating questions…</p>}
      {error && <p className="pdm__error">{error}</p>}
      {report && !loading && (
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
          <div className="pdm__footer-row">
            <button type="button" className="pdm__regenerate" onClick={() => load(true)}>Regenerate</button>
            {report.generated_at && (
              <span className="pdm__generated-at">Generated {new Date(report.generated_at).toLocaleDateString()}</span>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function InterviewTab({ project, token }) {
  return (
    <div className="pdm__tab-body">
      <IntelligenceBlock project={project} token={token} />
      <InterviewQuestionsBlock project={project} token={token} />
    </div>
  )
}

/* ───────────────────────── Tab 4 — Improve ───────────────────────── */
function ImproveTab({ recommendations, claimAudit }) {
  const fixes = claimAudit.report?.narrative?.fixes || []
  const hasAny = (recommendations && recommendations.length > 0) || fixes.length > 0

  if (!hasAny) {
    return <div className="pdm__tab-body"><p className="pdm__loading">No improvement suggestions for this project yet.</p></div>
  }

  return (
    <div className="pdm__tab-body">
      {recommendations?.length > 0 && (
        <div className="pdm__section">
          <span className="pdm__subsection-label">Highest Impact</span>
          <ul className="pdm__improve-list">
            {recommendations.map((r, i) => (
              <li key={i} className="pdm__improve-item">
                <span>{r.text}</span>
                {r.impact != null && r.impact > 0 && <span className="pdm__improve-impact">+{r.impact} pts</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {fixes.length > 0 && (
        <div className="pdm__section">
          <span className="pdm__subsection-label">Claim Fixes</span>
          <ul>{fixes.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

/* ───────────────────────── Panel shell ───────────────────────── */
function ProjectDetailModal({ project, recommendations, onClose, onLinkConfirmed }) {
  const { token } = useAuth()
  const [currentProject, setCurrentProject] = useState(project)
  const [activeTab, setActiveTab] = useState('overview')

  useEffect(() => { setCurrentProject(project); setActiveTab('overview') }, [project])

  useEffect(() => {
    function onKeyDown(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  const claimAudit = useClaimAudit(currentProject, token)

  function handleLinked(repoName) {
    setCurrentProject((prev) => ({ ...prev, has_repo: true, matched_repo_name: repoName }))
    onLinkConfirmed?.()
  }

  async function handleUnlink() {
    try {
      await unlinkProject(token, currentProject.id)
      setCurrentProject((prev) => ({ ...prev, has_repo: false, matched_repo_name: null }))
      onLinkConfirmed?.()
    } catch (err) {
      console.error('Failed to unlink project:', err)
    }
  }

  const scopedRecommendations = useMemo(() => {
    if (!recommendations || !currentProject) return []
    return recommendations.filter((r) => r.text?.includes(currentProject.name))
  }, [recommendations, currentProject])

  if (!currentProject) return null

  return (
    <>
      <div className="pdm__scrim" onClick={onClose} />
      <aside className="pdm__panel" role="dialog" aria-label={`${currentProject.name} details`}>
        <div className="pdm__header">
          <div className="pdm__header-main">
            <h2>{currentProject.name}</h2>
            <div className="pdm__header-facts">
              {currentProject.rating != null && currentProject.rating > 0 && <StarRating rating={currentProject.rating} size={12} />}
              <span className="pdm__header-tag">{currentProject.tier}</span>
              <span className="pdm__header-fact">{currentProject.collaboration_mode || 'Solo'}</span>
              {currentProject.has_repo && <span className="pdm__header-fact">GitHub</span>}
            </div>
          </div>
          <button type="button" className="pdm__close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <nav className="pdm__tabs" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.key}
              className={`pdm__tab ${activeTab === tab.key ? 'pdm__tab--active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="pdm__scroll">
          {activeTab === 'overview' && <OverviewTab project={currentProject} claimAudit={claimAudit} />}
          {activeTab === 'analysis' && (
            <AnalysisTab
              project={currentProject}
              token={token}
              claimAudit={claimAudit}
              onLinked={handleLinked}
              onUnlink={handleUnlink}
            />
          )}
          {activeTab === 'interview' && <InterviewTab project={currentProject} token={token} />}
          {activeTab === 'improve' && (
            <ImproveTab recommendations={scopedRecommendations} claimAudit={claimAudit} />
          )}
        </div>
      </aside>
    </>
  )
}

export default ProjectDetailModal