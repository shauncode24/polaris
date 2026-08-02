import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import {
  getProjectClaimAudit,
  getProjectIntelligence,
  getProjectInterviewQuestions,
  getLinkOptions,
  confirmProjectLink,
} from '../../api/projects'
import StarRating from './StarRating'
import './ProjectInspector.css'

const RISK_LABEL = { high: 'High risk', medium: 'Medium risk', low: 'Low risk' }
const DIFFICULTY_LABEL = { easy: 'Easy', medium: 'Medium', hard: 'Hard' }

// Same six angles InterviewToolkitPanel.jsx used to offer as a standalone
// sidebar card — now scoped to whichever project is open in the inspector
// instead of always meaning "your featured project" (doc: "Interview
// preparation belongs to a specific project").
const TOOLKIT_ACTIONS = [
  { key: 'explain_simply', label: 'Explain Simply' },
  { key: 'technical_deep_dive', label: 'Technical Deep Dive' },
  { key: 'architecture_review', label: 'Architecture Review' },
  { key: 'behavioral_stories', label: 'Behavioral Stories' },
  { key: 'recruiter_questions', label: 'Recruiter Questions' },
  { key: 'system_design', label: 'System Design Questions' },
]

function buildToolkitPrompt(action, projectName) {
  const subject = projectName ? ` about ${projectName}` : ''
  switch (action) {
    case 'explain_simply':
      return `Explain${subject} in plain terms, like you're describing it to a non-technical person.`
    case 'technical_deep_dive':
      return `Give me a technical deep dive${subject}, including the hardest engineering decision you made.`
    case 'architecture_review':
      return `Walk me through the architecture${subject} — strengths, weaknesses, and what you'd improve given more time.`
    case 'behavioral_stories':
      return `What behavioral stories (ownership, conflict, failure) does${subject.replace('about', '')} let me tell?`
    case 'recruiter_questions':
      return `What would a recruiter ask${subject} in a 20-second skim of my resume?`
    case 'system_design':
      return `Turn${subject} into a system design interview question and answer it the way you built it.`
    default:
      return `Tell me about${subject}.`
  }
}

function ClaimAuditSection({ project, token }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(true)
  const autoAppliedFor = useRef(null)

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

  // Auto-collapse only for low risk, and only once per project (doc:
  // "Collapse automatically when risk is Low. Expand automatically for
  // Medium or High.") — doesn't fight the user if they manually toggle it.
  useEffect(() => {
    if (report && autoAppliedFor.current !== project.id) {
      setExpanded(report.narrative.risk_level !== 'low')
      autoAppliedFor.current = project.id
    }
  }, [report, project.id])

  if (loading) return <p className="pin__loading">Checking resume claims against verified GitHub evidence…</p>
  if (error) return <p className="pin__error">{error}</p>
  if (!report) return null

  const { facts, narrative } = report

  return (
    <div className="pin__section">
      <button type="button" className="pin__section-header pin__section-header--toggle" onClick={() => setExpanded((v) => !v)}>
        <h3>Claim Audit</h3>
        <span className={`pin__risk-badge pin__risk-badge--${narrative.risk_level}`}>
          {RISK_LABEL[narrative.risk_level] || narrative.risk_level}
        </span>
      </button>
      {expanded && (
        <div className="pin__section-body">
          <p className="pin__headline">{narrative.headline}</p>

          {facts.architecture_flag && (
            <div className="pin__alert"><strong>Architecture mismatch:</strong> {facts.architecture_flag}</div>
          )}

          {facts.confirmed_claims?.length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label pin__subsection-label--success">Verified claims</span>
              <ul>{facts.confirmed_claims.map((c) => <li key={c}>{c}</li>)}</ul>
            </div>
          )}

          {facts.unsupported_claims.length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label pin__subsection-label--danger">Unsupported claims</span>
              <ul>{facts.unsupported_claims.map((c) => <li key={c}>{c}</li>)}</ul>
            </div>
          )}

          {facts.undersold_work.length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label pin__subsection-label--info">Undersold — real, verified, not on your resume</span>
              <ul>{facts.undersold_work.map((c) => <li key={c}>{c}</li>)}</ul>
            </div>
          )}

          {facts.verified_facts && Object.keys(facts.verified_facts).length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label pin__subsection-label--info">Verified GitHub evidence</span>
              <div className="pin__facts-grid">
                <div className="pin__fact"><strong>Quality</strong><span>{facts.verified_facts.quality_score ?? 0}/100</span></div>
                <div className="pin__fact"><strong>Activity</strong><span>{facts.verified_facts.activity_score ?? 0}/100</span></div>
                <div className="pin__fact"><strong>Architecture</strong><span>{facts.verified_facts.architecture_depth || 'None'}</span></div>
                <div className="pin__fact"><strong>Tests</strong><span>{facts.verified_facts.has_tests ? 'Yes' : 'No'}</span></div>
                <div className="pin__fact"><strong>CI/CD</strong><span>{facts.verified_facts.has_ci ? 'Yes' : 'No'}</span></div>
              </div>
              {(facts.verified_facts.technologies?.length > 0 || facts.verified_facts.capabilities?.length > 0) && (
                <div className="pin__facts-details">
                  {facts.verified_facts.technologies?.length > 0 && (
                    <p><strong>Verified tech:</strong> {facts.verified_facts.technologies.join(', ')}</p>
                  )}
                  {facts.verified_facts.capabilities?.length > 0 && (
                    <p><strong>Verified capabilities:</strong> {facts.verified_facts.capabilities.join(', ')}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {narrative.talking_points.length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label">Talking points</span>
              <ul>{narrative.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </div>
          )}

          {narrative.fixes.length > 0 && (
            <div className="pin__subsection">
              <span className="pin__subsection-label">Suggested fixes</span>
              <ul>{narrative.fixes.map((f, i) => <li key={i}>{f}</li>)}</ul>
            </div>
          )}

          {report.analysis_degraded && (
            <div className="pin__degraded">Claim audit analysis degraded — showing deterministic fallback.</div>
          )}

          <button type="button" className="pin__regenerate" onClick={() => load(true)}>Regenerate</button>
        </div>
      )}
    </div>
  )
}

// Explain + Compare live in the same section now (doc: "COMPARE PROJECTS —
// Remove the dedicated Compare section. Instead: Inside Project
// Intelligence → Compare With… → Select Project → Generate"). The backend
// endpoint already accepts an optional comparison_target, so this is a
// pure frontend simplification — one prompt-shaped form instead of two
// tabs, comparisonTarget just goes along for the ride when it's filled in.
function IntelligenceSection({ project, token }) {
  const [framing, setFraming] = useState(
    "Explain this project in technical depth, as if I'm interviewing at a top-tier tech company."
  )
  const [comparisonTarget, setComparisonTarget] = useState('')
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setReport(null)
    setError('')
    setComparisonTarget('')
  }, [project.id])

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
    <div className="pin__section">
      <div className="pin__section-header"><h3>Project Intelligence</h3></div>
      <div className="pin__section-body">
        <p className="pin__section-lead">
          Ask for a deep, framing-specific explanation — or compare this project against something else —
          grounded only in verified facts.
        </p>

        <label className="pin__field">
          <span>Framing</span>
          <textarea value={framing} onChange={(e) => setFraming(e.target.value)} rows={2} />
        </label>
        <label className="pin__field">
          <span>Compare with… (optional)</span>
          <input
            type="text"
            placeholder="e.g. Kong AI Gateway"
            value={comparisonTarget}
            onChange={(e) => setComparisonTarget(e.target.value)}
          />
        </label>

        <button type="button" className="pin__generate" onClick={() => generate(false)} disabled={loading}>
          {loading ? 'Generating…' : 'Generate'}
        </button>

        {error && <p className="pin__error">{error}</p>}

        {report && (
          <div className="pin__result">
            {report.insufficient_context ? (
              <p className="pin__error">{report.context_note || 'Not enough data on this project to answer that.'}</p>
            ) : (
              <>
                {report.comparison_target && (
                  <div className="pin__compare-heading">Comparing against: {report.comparison_target}</div>
                )}
                <p>{report.explanation}</p>
                {report.strongest_technical_decision && (
                  <div className="pin__subsection">
                    <span className="pin__subsection-label">Strongest technical decision</span>
                    <p>{report.strongest_technical_decision}</p>
                  </div>
                )}
                {report.weakest_point && (
                  <div className="pin__subsection">
                    <span className="pin__subsection-label">Weakest point</span>
                    <p>{report.weakest_point}</p>
                  </div>
                )}
                {report.comparison_notes && (
                  <div className="pin__subsection">
                    <span className="pin__subsection-label">Comparison notes</span>
                    <p>{report.comparison_notes}</p>
                  </div>
                )}
                {report.analysis_degraded && (
                  <div className="pin__degraded">Intelligence analysis degraded — showing deterministic fallback.</div>
                )}
                <div className="pin__footer-row">
                  <button type="button" className="pin__regenerate" onClick={() => generate(true)}>Regenerate</button>
                  {report.generated_at && (
                    <span className="pin__generated-at">Generated {new Date(report.generated_at).toLocaleDateString()}</span>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// Absorbs the old standalone InterviewToolkitPanel.jsx (quick-prompt chips
// that hand off to /interview) plus the grounded-questions generator that
// used to live in the modal. One "Interview Toolkit" section instead of
// two separate places to look for interview prep (doc requirement).
function InterviewSection({ project, token }) {
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setReport(null)
    setError('')
  }, [project.id])

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

  function handleToolkitClick(actionKey) {
    const prompt = buildToolkitPrompt(actionKey, project.name)
    navigate(`/interview?prefill=${encodeURIComponent(prompt)}`)
  }

  return (
    <div className="pin__section">
      <div className="pin__section-header"><h3>Interview Toolkit</h3></div>
      <div className="pin__section-body">
        <div className="pin__toolkit-grid">
          {TOOLKIT_ACTIONS.map((action) => (
            <button
              key={action.key}
              type="button"
              className="pin__toolkit-chip"
              onClick={() => handleToolkitClick(action.key)}
            >
              {action.label}
            </button>
          ))}
        </div>

        <div className="pin__toolkit-divider" />
        <h4 className="pin__toolkit-subheading">Grounded interview questions</h4>

        {!report && (
          <button type="button" className="pin__generate" onClick={() => load(false)} disabled={loading}>
            {loading ? 'Generating…' : 'Generate questions'}
          </button>
        )}
        {error && <p className="pin__error">{error}</p>}
        {report && (
          <>
            <ul className="pin__questions">
              {report.questions.map((q, i) => (
                <li key={i}>
                  <span className={`pin__difficulty pin__difficulty--${q.difficulty}`}>
                    {DIFFICULTY_LABEL[q.difficulty] || q.difficulty}
                  </span>
                  <div>
                    <p className="pin__question-text">{q.question}</p>
                    {q.grounded_in && <p className="pin__grounded-in">Grounded in: {q.grounded_in}</p>}
                  </div>
                </li>
              ))}
            </ul>
            {report.analysis_degraded && (
              <div className="pin__degraded">Interview questions analysis degraded — showing deterministic fallback.</div>
            )}
            <div className="pin__footer-row">
              <button type="button" className="pin__regenerate" onClick={() => load(true)}>Regenerate</button>
              {report.generated_at && (
                <span className="pin__generated-at">Generated {new Date(report.generated_at).toLocaleDateString()}</span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Persistent right-side inspector (doc: "PROJECT DETAIL EXPERIENCE — Do not
// use a centered popup. Open a persistent right-side inspector panel...
// Selecting another project immediately updates the panel."). Same data
// and same three backend-backed sections as the old ProjectDetailModal —
// only the shell changed, from a fixed overlay to a sticky sidebar that
// re-renders in place when `project` changes (each child section resets
// its own local state via `useEffect(..., [project.id])`).
function ProjectInspector({ project, onClose, onLinkConfirmed }) {
  const { token } = useAuth()
  const [availableRepos, setAvailableRepos] = useState([])
  const [selectedRepo, setSelectedRepo] = useState('')
  const [linking, setLinking] = useState(false)
  const [linkError, setLinkError] = useState('')

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  useEffect(() => {
    setSelectedRepo('')
    setLinkError('')
    if (!project.has_repo) {
      getLinkOptions(token)
        .then((data) => setAvailableRepos(data.repositories || []))
        .catch(() => setAvailableRepos([]))
    }
  }, [project.id, project.has_repo, token])

  async function handleLinkProject() {
    if (!selectedRepo) return
    setLinking(true)
    setLinkError('')
    try {
      await confirmProjectLink(token, project.id, selectedRepo)
      onLinkConfirmed?.()
    } catch (err) {
      setLinkError(err.message || 'Failed to connect repository.')
    } finally {
      setLinking(false)
    }
  }

  return (
    <aside className="pin">
      <div className="pin__header">
        <div className="pin__header-main">
          <h2>{project.name}</h2>
          <p className="pin__tagline">{project.tagline}</p>
          <div className="pin__header-meta">
            {project.rating != null && project.rating > 0 && <StarRating rating={project.rating} size={12} />}
            <span className="pin__meta-item">
              Updated {project.updated_at ? new Date(project.updated_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—'}
            </span>
            <span className="pin__meta-item">{project.collaboration_mode || 'Solo'}</span>
            {project.matched_repo_name && (
              <span className="pin__meta-item pin__meta-item--repo">{project.matched_repo_name}</span>
            )}
          </div>
        </div>
        <button type="button" className="pin__close" onClick={onClose} aria-label="Close">×</button>
      </div>

      <div className="pin__scroll">
        <div className="pin__section">
          <div className="pin__section-header"><h3>Overview</h3></div>
          <div className="pin__section-body">
            {project.description && <p className="pin__overview-desc">{project.description}</p>}
            {project.stack?.length > 0 && (
              <div className="pin__chip-row">
                {project.stack.map((tech) => <span key={tech} className="pin__chip">{tech}</span>)}
              </div>
            )}
            {project.capabilities?.length > 0 && (
              <div className="pin__chip-row">
                {project.capabilities.map((cap) => <span key={cap} className="pin__chip pin__chip--accent">{cap}</span>)}
              </div>
            )}
          </div>
        </div>

        {!project.has_repo && (
          <div className="pin__section">
            <div className="pin__link-container">
              <p className="pin__notice">
                No matched GitHub repository — claim audit and verified facts aren't available until this
                project is linked to a synced repo.
              </p>
              <div className="pin__link-row">
                <select value={selectedRepo} onChange={(e) => setSelectedRepo(e.target.value)} disabled={linking}>
                  <option value="">-- Select a repository --</option>
                  {availableRepos.map((repo) => <option key={repo} value={repo}>{repo}</option>)}
                </select>
                <button type="button" onClick={handleLinkProject} disabled={linking || !selectedRepo} className="pin__link-button">
                  {linking ? 'Linking…' : 'Connect'}
                </button>
              </div>
              {linkError && <p className="pin__link-error">{linkError}</p>}
            </div>
          </div>
        )}

        {project.has_repo && <ClaimAuditSection project={project} token={token} />}
        <IntelligenceSection project={project} token={token} />
        <InterviewSection project={project} token={token} />
      </div>
    </aside>
  )
}

export default ProjectInspector