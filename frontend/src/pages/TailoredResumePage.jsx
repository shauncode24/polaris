import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listJobIntelligenceProfiles } from '../api/jobIntelligence'
import { changeTailoredResume, generateTailoredResume, getTailoredResume } from '../api/tailoredResume'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ContactHeader from '../components/resume/tailored/ContactHeader'
import ResumeSections from '../components/resume/tailored/ResumeSections'
import ScorePanel from '../components/resume/tailored/ScorePanel'
import './TailoredResumePage.css'

function jobLabel(job) {
  const name = [job.role || 'Untitled role', job.company].filter(Boolean).join(' @ ')
  return job.is_primary ? `${name} (primary target)` : name
}

function allLines(document) {
  const entries = [...document.experience, ...document.projects, ...document.education]
  return [...(document.summary ? [document.summary] : []), ...entries.flatMap((entry) => entry.bullets)]
}

export default function TailoredResumePage() {
  const { token } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  const [jobs, setJobs] = useState(null) // null until loaded
  const [view, setView] = useState(null)
  const [loading, setLoading] = useState(false)
  const [generatingFor, setGeneratingFor] = useState(null) // job ids being generated
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [lineError, setLineError] = useState(null) // { id, message }

  const requested = searchParams.get('jobId')
  // The list puts the primary target first.
  const jobId = jobs?.find((job) => job.id === requested)?.id ?? jobs?.[0]?.id ?? null
  // Counts what is being looked at, so a late reply about something else is dropped.
  const shown = useRef(0)
  const openJob = useRef(null)
  openJob.current = jobId

  useEffect(() => {
    let cancelled = false
    listJobIntelligenceProfiles(token)
      .then((items) => { if (!cancelled) setJobs(items) })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Could not load your saved jobs.')
        setJobs([])
      })
    return () => { cancelled = true }
  }, [token])

  async function load(id, version = null) {
    const request = ++shown.current
    setLoading(true)
    setError('')
    setLineError(null)
    try {
      const data = await getTailoredResume(token, id, version)
      if (request === shown.current) setView(data)
    } catch (err) {
      if (request === shown.current) {
        setError(err.message)
        setView(null)
      }
    } finally {
      if (request === shown.current) setLoading(false)
    }
  }

  useEffect(() => {
    if (jobId) load(jobId)
    return () => { shown.current += 1 }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, token])

  async function generate() {
    const target = jobId
    setGeneratingFor(target)
    setError('')
    try {
      const data = await generateTailoredResume(token, target)
      if (openJob.current === target) {
        shown.current += 1 // anything still loading is older than this
        setView(data)
        setLoading(false)
      }
    } catch (err) {
      if (openJob.current === target) setError(err.message)
    } finally {
      setGeneratingFor(null)
    }
  }

  // Saves a change to the version on screen; resolves to whether it worked. An
  // error is shown beside what `lineId` names: a line, or the contact details.
  async function save(changes, lineId = null) {
    const request = shown.current
    setSaving(true)
    setError('')
    setLineError(null)
    try {
      const data = await changeTailoredResume(token, view.job.id, view.resume.version, changes)
      if (request === shown.current) setView(data)
      return true
    } catch (err) {
      if (request === shown.current) {
        if (lineId) setLineError({ id: lineId, message: err.message })
        else setError(err.message)
      }
      return false
    } finally {
      setSaving(false)
    }
  }

  // Nothing from another job stays on screen while this one loads.
  const current = view && view.job.id === jobId ? view : null
  const resume = current?.resume
  const generating = generatingFor !== null
  // No choices while this job's next version is being made: it would replace them on screen.
  const busy = saving || (generating && generatingFor === jobId)
  const waiting = resume
    ? allLines(resume.document).filter((line) => line.rewrite && line.decision === 'pending').length
    : 0

  function lineProps(line) {
    return {
      line,
      evidence: resume.evidence,
      busy,
      error: lineError?.id === line.id ? lineError.message : null,
      onChange: (change) => save({ lines: [{ line_id: line.id, ...change }] }, line.id),
    }
  }

  return (
    <div className="tr-layout">
      <Sidebar />
      <div className="tr-main">
        <TopBar section="Profile" page="Tailored Resume" />
        <div className="tr-content">
          <div>
            <h1 className="tr-title">Tailored Resume</h1>
            <p className="tr-subtitle">
              Your own evidence, chosen for one job. A suggested rewording appears on the resume only after you accept it.
            </p>
          </div>

          {error && <div className="tr-banner tr-banner--error" role="alert">{error}</div>}

          {jobs === null && <p className="tr-hint">Loading your jobs…</p>}

          {jobs?.length === 0 && !error && (
            <div className="tr-card">
              <p>Add a job description first: the resume is tailored to it.</p>
              <Link to="/job-intelligence" className="tr-btn tr-btn--primary">Add a job</Link>
            </div>
          )}

          {jobId && (
            <div className="tr-card tr-toolbar">
              <label>
                <span className="tr-label">Job</span>
                <select value={jobId} onChange={(event) => setSearchParams({ jobId: event.target.value })}>
                  {jobs.map((job) => <option key={job.id} value={job.id}>{jobLabel(job)}</option>)}
                </select>
              </label>

              {resume && current.versions.length > 1 && (
                <label>
                  <span className="tr-label">Version</span>
                  <select
                    value={resume.version}
                    disabled={saving}
                    onChange={(event) => load(jobId, Number(event.target.value))}
                  >
                    {current.versions.map((number) => <option key={number} value={number}>Version {number}</option>)}
                  </select>
                </label>
              )}

              <button
                type="button"
                className="tr-btn tr-btn--primary"
                disabled={!current || loading || generating || saving}
                onClick={generate}
              >
                {generating ? 'Generating…' : resume ? 'Generate new version' : 'Generate resume'}
              </button>
            </div>
          )}

          {generatingFor === jobId && jobId && (
            <p className="tr-hint" role="status">Choosing your evidence and writing suggestions. This can take a minute.</p>
          )}
          {loading && <p className="tr-hint">Loading…</p>}

          {current && !resume && !loading && !generating && (
            <div className="tr-card">
              <p>No resume for this job yet. Generate one to choose your most relevant work and get suggested wording.</p>
            </div>
          )}

          {resume && !loading && (
            <>
              {resume.stale && (
                <div className="tr-banner">
                  Your profile has changed since this version was made. Generate a new version to include the changes.
                </div>
              )}
              {resume.document.notice && <div className="tr-banner">{resume.document.notice}</div>}
              <ScorePanel score={resume.score} />
              <p className="tr-hint">
                {waiting === 0
                  ? 'No suggestions are waiting for you.'
                  : `${waiting} suggestion${waiting === 1 ? ' is' : 's are'} waiting for your decision.`}
                {' '}Changes are saved to version {resume.version} as you make them.
              </p>

              {/* Remounted per version, so no half-finished edit carries over. */}
              <article className="tr-card tr-paper" key={`${jobId}-${resume.version}`}>
                <ContactHeader
                  header={resume.document.header}
                  busy={busy}
                  error={lineError?.id === 'contact' ? lineError.message : null}
                  onChange={(contact) => save({ contact }, 'contact')}
                />
                <ResumeSections
                  document={resume.document}
                  evidence={resume.evidence}
                  busy={busy}
                  lineProps={lineProps}
                  onReorder={(order) => save({ section_order: order })}
                />
              </article>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
