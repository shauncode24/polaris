import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import { analyzeJobText, analyzeJobPdf, listJobAnalyses, getJobAnalysis } from '../api/jobs'
import JobDescriptionForm from '../components/jobs/JobDescriptionForm'
import JobAnalysisResults from '../components/jobs/JobAnalysisResults'
import PastAnalysesPanel from '../components/jobs/PastAnalysesPanel'
import HistoryPopover from '../components/jobs/HistoryPopover'
import AnalyzingProgress from '../components/jobs/AnalyzingProgress'
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
  const [currentMeta, setCurrentMeta] = useState(null) // { role, company }

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
        const items = await listJobAnalyses(token)
        if (cancelled) return
        setHistory(items)
        if (items.length > 0) {
          await selectAnalysis(items[0].id, items)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load your past analyses.')
      } finally {
        if (!cancelled) setHistoryLoading(false)
      }
    }

    loadHistory()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function selectAnalysis(jobId, sourceList = history) {
    setSelectedId(jobId)
    setResultsLoading(true)
    setError('')
    try {
      const data = await getJobAnalysis(token, jobId)
      setResults(data)
      const meta = sourceList.find((h) => h.id === jobId)
      setCurrentMeta(meta ? { role: meta.role, company: meta.company } : null)
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
      setCurrentMeta({ role: role || null, company: company || null })
      setSelectedId(null)

      try {
        const items = await listJobAnalyses(token)
        setHistory(items)
        if (items.length > 0) {
          setSelectedId(items[0].id)
          setCurrentMeta({ role: items[0].role, company: items[0].company })
        }
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

  function handleNewAnalysis() {
    setResults(null)
    setSelectedId(null)
    setCurrentMeta(null)
    setError('')
  }

  const roleLabel = currentMeta?.company
    ? `${currentMeta.role || 'this role'} at ${currentMeta.company}`
    : currentMeta?.role

  return (
    <div className="job-analyzer-layout">
      <Sidebar />
      <div className="job-analyzer-main">
        <TopBar
          section="Analyze"
          page="Skill Gap Analyzer"
          hideSearch
          hideNotifications
          actions={
            results ? (
              <>
                <HistoryPopover items={history} selectedId={selectedId} onSelect={selectAnalysis} loading={historyLoading} />
                <button type="button" className="job-analyzer-new-btn" onClick={handleNewAnalysis}>
                  + New analysis
                </button>
              </>
            ) : null
          }
        />

        <div className="job-analyzer-content">
          {!results && (
            <>
              <div className="job-analyzer-intro">
                <h1>Skill Gap Analyzer</h1>
                <p>Paste a job description to see how you match.</p>
              </div>

              <div className="job-analyzer-columns">
                <PastAnalysesPanel items={history} selectedId={selectedId} onSelect={selectAnalysis} loading={historyLoading} />

                {loading ? (
                  <AnalyzingProgress stages={STAGES} activeIndex={stageIndex} />
                ) : (
                  <JobDescriptionForm onSubmit={handleSubmit} loading={loading} />
                )}
              </div>

              {error && <p className="job-analyzer-error">{error}</p>}
            </>
          )}

          {results && (
            <>
              {resultsLoading ? (
                <p className="job-analyzer-loading-results">Loading analysis…</p>
              ) : (
                <JobAnalysisResults data={results} jobId={selectedId} roleLabel={roleLabel} />
              )}
              {error && <p className="job-analyzer-error">{error}</p>}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default JobAnalyzerPage