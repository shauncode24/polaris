import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { IconCompass } from '../components/icons/Icons'
import ThemeToggle from '../components/auth/ThemeToggle'
import { analyzeJobText, analyzeJobPdf } from '../api/jobs'
import JobDescriptionForm from '../components/jobs/JobDescriptionForm'
import JobAnalysisResults from '../components/jobs/JobAnalysisResults'
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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [results, setResults] = useState(null)
  const [stageIndex, setStageIndex] = useState(0)

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

        {results && <JobAnalysisResults data={results} />}
      </main>
    </div>
  )
}

export default JobAnalyzerPage