import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listJobIntelligenceProfiles } from '../api/jobIntelligence'
import { generateInterviewKit, getInterviewKit, matchKitEvidence } from '../api/interviewKit'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ProgressSummary from '../components/interview/kit/ProgressSummary'
import QuestionCard from '../components/interview/kit/QuestionCard'
import StudyPlanPanel from '../components/interview/kit/StudyPlanPanel'
import { CATEGORY_LABELS } from '../components/interview/kit/labels'
import './InterviewKitPage.css'

const STUDY = 'study'

function jobLabel(job) {
  const name = [job.role || 'Untitled role', job.company].filter(Boolean).join(' @ ')
  return job.is_primary ? `${name} (primary target)` : name
}

export default function InterviewKitPage() {
  const { token } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()

  const [jobs, setJobs] = useState(null) // null until loaded
  const [page, setPage] = useState(null)
  const [loading, setLoading] = useState(false)
  const [working, setWorking] = useState(null) // { jobId, message } while a kit is made or matched
  const [tab, setTab] = useState(null)
  const [revision, setRevision] = useState(0) // bumped when practice or the kit changes
  const [error, setError] = useState('')

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
    try {
      const data = await getInterviewKit(token, id, version)
      if (request === shown.current) setPage(data)
    } catch (err) {
      if (request === shown.current) {
        setError(err.message)
        setPage(null)
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

  // Makes a new version, or matches this one again, and shows the result unless
  // another job has been opened meanwhile.
  async function change(message, request) {
    const target = jobId
    setWorking({ jobId: target, message })
    setError('')
    try {
      const data = await request(target)
      if (openJob.current === target) {
        shown.current += 1 // anything still loading is older than this
        setPage(data)
        setLoading(false)
        setRevision((number) => number + 1)
      }
    } catch (err) {
      if (openJob.current === target) setError(err.message)
    } finally {
      setWorking(null)
    }
  }

  // Nothing from another job stays on screen while this one loads.
  const current = page && page.job.id === jobId ? page : null
  const kit = current?.kit

  // Reloads scores and progress without disturbing what is open on screen.
  async function refresh() {
    const request = shown.current
    setRevision((number) => number + 1)
    try {
      const data = await getInterviewKit(token, current.job.id, kit.version)
      if (request === shown.current) setPage(data)
    } catch (err) {
      if (request === shown.current) setError(`Your answer is saved, but progress didn't refresh. ${err.message}`)
    }
  }

  const categories = kit?.categories.map((c) => c.category) ?? []
  const tabs = [...categories, STUDY]
  const openTab = tabs.includes(tab) ? tab : tabs[0]
  const busy = working !== null

  function moveTab(event) {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key]
    if (!step) return
    event.preventDefault()
    const next = tabs[(tabs.indexOf(openTab) + step + tabs.length) % tabs.length]
    setTab(next)
    document.getElementById(`ik-tab-${next}`)?.focus()
  }

  return (
    <div className="ik-layout">
      <Sidebar />
      <div className="ik-main">
        <TopBar section="Interview" page="Interview Kit" hideSearch hideNotifications />
        <div className="ik-content">
          <div>
            <h1 className="ik-title">Interview Kit</h1>
            <p className="ik-hint">
              Questions for one job, each matched to your own work. Practise them and see what to study.
            </p>
          </div>

          {error && <div className="ik-banner ik-banner--error" role="alert">{error}</div>}

          {jobs === null && <p className="ik-hint">Loading your jobs…</p>}

          {jobs?.length === 0 && !error && (
            <div className="ik-card">
              <p>Add a job description first: the questions come from it.</p>
              <Link to="/job-intelligence" className="ik-btn ik-btn--primary">Add a job</Link>
            </div>
          )}

          {jobId && (
            <div className="ik-card ik-toolbar">
              <label>
                <span className="ik-label">Job</span>
                <select value={jobId} onChange={(event) => setSearchParams({ jobId: event.target.value })}>
                  {jobs.map((job) => <option key={job.id} value={job.id}>{jobLabel(job)}</option>)}
                </select>
              </label>

              {kit && current.versions.length > 1 && (
                <label>
                  <span className="ik-label">Version</span>
                  <select
                    value={kit.version}
                    disabled={busy}
                    onChange={(event) => load(jobId, Number(event.target.value))}
                  >
                    {current.versions.map((number) => <option key={number} value={number}>Version {number}</option>)}
                  </select>
                </label>
              )}

              <button
                type="button"
                className="ik-btn ik-btn--primary"
                disabled={!current || loading || busy}
                onClick={() => change(
                  'Choosing questions and matching them to your work. This can take a minute.',
                  (id) => generateInterviewKit(token, id),
                )}
              >
                {kit ? 'Generate new version' : 'Generate kit'}
              </button>
            </div>
          )}

          {working && working.jobId === jobId && <p className="ik-hint" role="status">{working.message}</p>}
          {loading && <p className="ik-hint">Loading…</p>}

          {current && !kit && !loading && !busy && (
            <div className="ik-card">
              <p>No kit for this job yet. Generate one to get questions matched to your projects and experience.</p>
            </div>
          )}

          {kit && !loading && (
            <>
              {kit.stale && (
                <div className="ik-banner">
                  <span>Your profile has changed since these questions were matched to your work.</span>
                  <button
                    type="button"
                    className="ik-btn"
                    disabled={busy}
                    onClick={() => change(
                      'Matching your work to the questions…',
                      (id) => matchKitEvidence(token, id, kit.version),
                    )}
                  >
                    Match again
                  </button>
                </div>
              )}
              {kit.notice && <div className="ik-banner">{kit.notice}</div>}
              {kit.evidence_notice && <div className="ik-banner">{kit.evidence_notice}</div>}
              <ProgressSummary kit={kit} />
            </>
          )}

          {current && !loading && (
            <>
              <div className="ik-tabs" role="tablist" aria-label="Question categories" onKeyDown={moveTab}>
                {tabs.map((name) => {
                  const counts = kit?.categories.find((c) => c.category === name)
                  return (
                    <button
                      key={name}
                      id={`ik-tab-${name}`}
                      type="button"
                      role="tab"
                      aria-selected={openTab === name}
                      aria-controls={`ik-panel-${name}`}
                      tabIndex={openTab === name ? 0 : -1}
                      className="ik-tab"
                      onClick={() => setTab(name)}
                    >
                      {name === STUDY ? 'Study plan' : CATEGORY_LABELS[name]}
                      {counts && <span>{counts.practised}/{counts.total}</span>}
                    </button>
                  )
                })}
              </div>

              {/* All categories stay mounted, so an answer being written or
                  reviewed isn't lost by looking at another. Remounted per
                  version, so nothing carries over between kits. */}
              {categories.map((category) => (
                <div
                  key={`${jobId}-${kit.version}-${category}`}
                  id={`ik-panel-${category}`}
                  role="tabpanel"
                  aria-labelledby={`ik-tab-${category}`}
                  hidden={openTab !== category}
                >
                  <ul className="ik-questions">
                    {kit.questions.filter((q) => q.category === category).map((question) => (
                      <QuestionCard key={question.id} token={token} question={question} onPractised={refresh} />
                    ))}
                  </ul>
                </div>
              ))}

              {openTab === STUDY && (
                <div id={`ik-panel-${STUDY}`} role="tabpanel" aria-labelledby={`ik-tab-${STUDY}`}>
                  <StudyPlanPanel token={token} jobId={jobId} revision={revision} />
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
