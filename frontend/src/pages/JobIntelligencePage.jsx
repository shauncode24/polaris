// frontend/src/pages/JobIntelligencePage.jsx
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import {
  analyzeJobIntelligenceText,
  analyzeJobIntelligencePdf,
  listJobIntelligenceProfiles,
  getJobIntelligenceProfile,
  setPrimaryJob,
  deleteJob,
  compareJobs,
} from '../api/jobIntelligence'
import JobIntelligenceForm from '../components/job-intelligence/JobIntelligenceForm'
import JobIntelligenceResults from '../components/job-intelligence/JobIntelligenceResults'
import JobLibrary from '../components/job-intelligence/JobLibrary'
import JobComparison from '../components/job-intelligence/JobComparison'
import AnalyzingJobIntelligence from '../components/job-intelligence/AnalyzingJobIntelligence'
import './JobIntelligencePage.css'

const STAGES = [
  'Reading job description',
  'Running the combined extraction',
  'Normalizing role skills',
  'Determining seniority',
  'Deriving resume keywords & interview focus',
]

function JobIntelligencePage() {
  const { token } = useAuth()

  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [jobsBusy, setJobsBusy] = useState(false)
  const [comparison, setComparison] = useState(null)

  const [loading, setLoading] = useState(false)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadJobs() {
      setJobsLoading(true)
      try {
        const items = await listJobIntelligenceProfiles(token)
        if (!cancelled) setJobs(items)
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load your saved jobs.')
      } finally {
        if (!cancelled) setJobsLoading(false)
      }
    }

    loadJobs()
    return () => { cancelled = true }
  }, [token])

  // One library action at a time; the list is re-read after a change.
  async function runLibraryAction(action, failure) {
    setJobsBusy(true)
    setError('')
    try {
      await action()
    } catch (err) {
      setError(err.message || failure)
    } finally {
      setJobsBusy(false)
    }
  }

  function handleSetPrimary(id, primary) {
    runLibraryAction(async () => {
      await setPrimaryJob(token, id, primary)
      setJobs(await listJobIntelligenceProfiles(token))
    }, 'Could not change the primary target.')
  }

  function handleDelete(id) {
    runLibraryAction(async () => {
      await deleteJob(token, id)
      setJobs(await listJobIntelligenceProfiles(token))
    }, 'Could not delete this job.')
  }

  function handleCompare(ids) {
    runLibraryAction(async () => {
      setComparison(await compareJobs(token, ids))
    }, 'Could not compare these jobs.')
  }

  async function openJob(jobIntelligenceId) {
    setResultsLoading(true)
    setError('')
    try {
      const data = await getJobIntelligenceProfile(token, jobIntelligenceId)
      setResults(data)
    } catch (err) {
      setError(err.message || 'Could not load this role.')
    } finally {
      setResultsLoading(false)
    }
  }

  async function handleSubmit({ mode, text, file, company, role }) {
    setLoading(true)
    setError('')
    setResults(null)
    setStageIndex(0)

    const ticker = setInterval(() => {
      setStageIndex((i) => (i < STAGES.length - 1 ? i + 1 : i))
    }, 900)

    try {
      const data =
        mode === 'text'
          ? await analyzeJobIntelligenceText(token, { rawText: text, company, role })
          : await analyzeJobIntelligencePdf(token, file, { company, role })
      setResults(data)

      try {
        setJobs(await listJobIntelligenceProfiles(token))
      } catch {
        // Non-fatal — the result is already shown even if the list refresh fails.
      }
    } catch (err) {
      setError(err.message || 'Something went wrong extracting this role.')
    } finally {
      clearInterval(ticker)
      setLoading(false)
    }
  }

  function showLibrary() {
    setResults(null)
    setComparison(null)
    setError('')
  }

  const showingDetail = results || comparison || resultsLoading

  return (
    <div className="ji-page-layout">
      <Sidebar />
      <div className="ji-page-main">
        <TopBar
          section="Understand"
          page="Job & Company Intelligence"
          hideSearch
          hideNotifications
          actions={
            showingDetail ? (
              <button type="button" className="ji-page-new-btn" onClick={showLibrary}>
                ← Your jobs
              </button>
            ) : null
          }
        />

        <div className="ji-page-content">
          {!showingDetail && (
            <>
              <div className="ji-page-intro">
                <h1>Job & Company Intelligence</h1>
                <p>Add the jobs you&apos;re interested in, compare how well you match them, and pick the one to prepare for.</p>
              </div>

              <div className="ji-page-columns">
                <JobLibrary
                  items={jobs}
                  loading={jobsLoading}
                  busy={jobsBusy}
                  onOpen={openJob}
                  onSetPrimary={handleSetPrimary}
                  onDelete={handleDelete}
                  onCompare={handleCompare}
                />

                {loading ? (
                  <AnalyzingJobIntelligence stages={STAGES} activeIndex={stageIndex} />
                ) : (
                  <JobIntelligenceForm onSubmit={handleSubmit} loading={loading} />
                )}
              </div>

              {error && <p className="ji-page-error">{error}</p>}
            </>
          )}

          {showingDetail && (
            <>
              {resultsLoading ? (
                <p className="ji-page-loading-results">Loading role…</p>
              ) : comparison ? (
                <JobComparison data={comparison} />
              ) : (
                <JobIntelligenceResults data={results} />
              )}
              {error && <p className="ji-page-error">{error}</p>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default JobIntelligencePage