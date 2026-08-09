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
} from '../api/jobIntelligence'
import JobIntelligenceForm from '../components/job-intelligence/JobIntelligenceForm'
import JobIntelligenceResults from '../components/job-intelligence/JobIntelligenceResults'
import JobIntelligenceHistoryPanel from '../components/job-intelligence/JobIntelligenceHistoryPanel'
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

  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)

  const [loading, setLoading] = useState(false)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [stageIndex, setStageIndex] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      setHistoryLoading(true)
      try {
        const items = await listJobIntelligenceProfiles(token)
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) {
          await selectProfile(items[0].id)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load your role history.')
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    }

    loadHistory()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function selectProfile(jobIntelligenceId) {
    setSelectedId(jobIntelligenceId)
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
      setSelectedId(data.job_intelligence?.id || null)

      try {
        const items = await listJobIntelligenceProfiles(token)
        setHistory(items)
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

  function handleNewExtraction() {
    setResults(null)
    setSelectedId(null)
    setError('')
  }

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
            results ? (
              <button type="button" className="ji-page-new-btn" onClick={handleNewExtraction}>
                + New extraction
              </button>
            ) : null
          }
        />

        <div className="ji-page-content">
          {!results && (
            <>
              <div className="ji-page-intro">
                <h1>Job & Company Intelligence</h1>
                <p>Paste a job description to understand the role and company on their own — no comparison against your profile.</p>
              </div>

              <div className="ji-page-columns">
                <JobIntelligenceHistoryPanel items={history} selectedId={selectedId} onSelect={selectProfile} loading={historyLoading} />

                {loading ? (
                  <AnalyzingJobIntelligence stages={STAGES} activeIndex={stageIndex} />
                ) : (
                  <JobIntelligenceForm onSubmit={handleSubmit} loading={loading} />
                )}
              </div>

              {error && <p className="ji-page-error">{error}</p>}
            </>
          )}

          {results && (
            <>
              {resultsLoading ? (
                <p className="ji-page-loading-results">Loading role…</p>
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