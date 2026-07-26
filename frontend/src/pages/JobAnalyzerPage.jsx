import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { IconCompass } from '../components/icons/Icons'
import ThemeToggle from '../components/auth/ThemeToggle'
import { analyzeJobText, analyzeJobPdf, listJobAnalyses, getJobAnalysis } from '../api/jobs'
import JobDescriptionForm from '../components/jobs/JobDescriptionForm'
import JobAnalysisResults from '../components/jobs/JobAnalysisResults'
import JobAnalysisHistory from '../components/jobs/JobAnalysisHistory'
import './JobAnalyzerPage.css'

const STAGES = [
  'Reading job description',
  'Extracting required skills',
  'Comparing with your profile',
  'Measuring skill gaps',
  'Building career report',
]

function JobAnalyzerPage() {
  const { token } = useAuth()

  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)

  const [loading, setLoading] = useState(false)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [stageIndex, setStageIndex] = useState(0)

  // On arrival: fetch every past analysis for this user, and load the
  // most recent one's full report so the page never opens empty if
  // work has already been done.
  useEffect(() => {
    let cancelled = false

    async function loadHistory() {
      setHistoryLoading(true)
      try {
        const items = await listJobAnalyses(token)
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) {
          await selectAnalysis(items[0].id, { skipHistoryReload: true })
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load your past analyses.')
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    }

    loadHistory()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function selectAnalysis(jobId) {
    setSelectedId(jobId)
    setResultsLoading(true)
    setError('')
    try {
      const data = await getJobAnalysis(token, jobId)
      setResults(data)
    } catch (err) {
      setError(err.message || 'Could not load this analysis.')
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
          ? await analyzeJobText(token, { rawText: text, company, role })
          : await analyzeJobPdf(token, file, { company, role })
      setResults(data)
      setSelectedId(null) // freshly-run analysis isn't in the history list's ids yet

      // Refresh history in the background so the new run appears at the top.
      try {
        const items = await listJobAnalyses(token)
        setHistory(items)
        if (items.length > 0) setSelectedId(items[0].id)
      } catch {
        // Non-fatal — the result is already shown even if the list refresh fails.
      }
    } catch (err) {
      setError(err.message || 'Something went wrong analyzing this job description.')
    } finally {
      clearInterval(ticker)
      setLoading(false)
    }
  }

  return (
    <div className="job-analyzer-page">
      <header className="job-analyzer-page__header">
        <span className="job-analyzer-page__brand">
          <IconCompass size={18} /> Polaris
        </span>
        <ThemeToggle />
      </header>

      <main className="job-analyzer-page__main">
        <h1>Analyze a Job Opportunity</h1>
        <p className="job-analyzer-page__lead">
          Paste or upload a job description to see how well your current profile matches the role.
        </p>

        <JobDescriptionForm onSubmit={handleSubmit} loading={loading} />

        {loading && (
          <ul className="job-analyzer-page__stages">
            {STAGES.map((stage, i) => (
              <li key={stage} className={i <= stageIndex ? 'is-active' : ''}>
                {i < stageIndex ? '✓' : '…'} {stage}
              </li>
            ))}
          </ul>
        )}

        {error && <p className="job-analyzer-page__error">{error}</p>}

        <JobAnalysisHistory
          items={history}
          selectedId={selectedId}
          onSelect={selectAnalysis}
          loading={historyLoading}
        />

        {resultsLoading && !loading && (
          <p className="job-analyzer-page__loading-results">Loading analysis…</p>
        )}

        {results && !resultsLoading && <JobAnalysisResults data={results} />}
      </main>
    </div>
  )
}

export default JobAnalyzerPage