import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import { listParsedJobs, getSkillGapForJob } from '../api/skillGap'
import SkillGapJobSelector from '../components/jobs/SkillGapJobSelector'
import SkillGapResults from '../components/jobs/SkillGapResults'
import './JobAnalyzerPage.css'

function JobAnalyzerPage() {
  const { token } = useAuth()

  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [selectedId, setSelectedId] = useState(null)

  const [results, setResults] = useState(null)
  const [resultsLoading, setResultsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false

    async function loadJobs() {
      setJobsLoading(true)
      try {
        const items = await listParsedJobs(token)
        if (cancelled) return
        setJobs(items)
        if (items.length > 0) {
          setSelectedId(items[0].id)
        }
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load your parsed roles.')
      } finally {
        if (!cancelled) setJobsLoading(false)
      }
    }

    loadJobs()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    if (!selectedId) return
    let cancelled = false

    async function loadResults() {
      setResultsLoading(true)
      setError('')
      try {
        const data = await getSkillGapForJob(token, selectedId)
        if (!cancelled) setResults(data)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Something went wrong analyzing this match.')
          setResults(null)
        }
      } finally {
        if (!cancelled) setResultsLoading(false)
      }
    }

    loadResults()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, token])

  async function handleRegenerate() {
    if (!selectedId) return
    setResultsLoading(true)
    setError('')
    try {
      const data = await getSkillGapForJob(token, selectedId, { regenerate: true })
      setResults(data)
    } catch (err) {
      setError(err.message || 'Something went wrong re-analyzing this match.')
    } finally {
      setResultsLoading(false)
    }
  }

  function handleSelect(id) {
    setSelectedId(id)
    setResults(null)
  }

  return (
    <div className="job-analyzer-layout">
      <Sidebar />
      <div className="job-analyzer-main">
        <TopBar section="Analyze" page="Skill Gap" hideSearch hideNotifications />

        <div className="job-analyzer-content">
          <div className="job-analyzer-intro">
            <h1>Skill Gap</h1>
            <p>How well does your current engineering profile match this specific job — and where are the gaps?</p>
          </div>

          <SkillGapJobSelector jobs={jobs} selectedId={selectedId} onSelect={handleSelect} loading={jobsLoading} />

          {error && <p className="job-analyzer-error">{error}</p>}

          {!jobsLoading && jobs.length > 0 && !selectedId && (
            <p className="job-analyzer-loading-results">Select a role above to see your match.</p>
          )}

          {selectedId && resultsLoading && (
            <div className="sg-loading-card">
              <span className="sg-loading-spinner" />
              <p>Comparing your Engineering Identity against this role…</p>
            </div>
          )}

          {selectedId && !resultsLoading && results && (
            <SkillGapResults data={results} onRegenerate={handleRegenerate} />
          )}
        </div>
      </div>
    </div>
  )
}

export default JobAnalyzerPage