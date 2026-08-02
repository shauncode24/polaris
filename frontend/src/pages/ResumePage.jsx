import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { getResumeWorkspace, uploadResume, runResumeReview, runResumeAnalysis, getResumeCoherence, getResumeTailoring, getResumeEvolution } from '../api/resume'
import { listJobAnalyses } from '../api/jobs'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ResumeHeader from '../components/resume/ResumeHeader'
import ResumePdfViewer from '../components/resume/ResumePdfViewer'
import ExecutiveSummary from '../components/resume/ExecutiveSummary'
import PriorityFixes from '../components/resume/PriorityFixes'

import ResumeAnalysisPanel from '../components/resume/ResumeAnalysisPanel'
import ResumeReviewPanel from '../components/resume/ResumeReviewPanel'
import SkillsCoveragePanel from '../components/resume/SkillsCoveragePanel'
import ResumeVsJobsPanel from '../components/resume/ResumeVsJobsPanel'
import ResumeEvolution from '../components/resume/ResumeEvolution'
import ResumeCoherence from '../components/resume/ResumeCoherence'
import ResumeTailoring from '../components/resume/ResumeTailoring'
import './ResumePage.css'

export default function ResumePage() {
  const { token } = useAuth()
  const uploadInputRef = useRef(null)

  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [analyzeLoading, setAnalyzeLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showPreview, setShowPreview] = useState(false)

  // Evolution
  const [evolution, setEvolution] = useState(null)

  // Coherence
  const [coherence, setCoherence] = useState(null)
  const [coherenceLoading, setCoherenceLoading] = useState(false)
  const [coherenceError, setCoherenceError] = useState(null)

  // Tailoring
  const [tailoring, setTailoring] = useState(null)
  const [tailoringLoading, setTailoringLoading] = useState(false)
  const [tailoringError, setTailoringError] = useState(null)
  const [jobs, setJobs] = useState([])

  async function loadWorkspace() {
    try {
      const data = await getResumeWorkspace(token)
      setWorkspace(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function loadEvolution() {
    try {
      const data = await getResumeEvolution(token)
      setEvolution(data)
    } catch (_) {
      // Evolution is non-critical — silently ignore
    }
  }

  async function loadJobs() {
    try {
      const data = await listJobAnalyses(token)
      setJobs(Array.isArray(data) ? data : data?.items ?? [])
    } catch (_) {}
  }

  useEffect(() => {
    loadWorkspace()
    loadEvolution()
    loadJobs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function handleUpload(file) {
    if (!file) return
    setUploadLoading(true)
    try {
      await uploadResume(file, token)
      setLoading(true)
      await loadWorkspace()
      await loadEvolution()
    } catch (e) {
      setError(e.message)
    } finally {
      setUploadLoading(false)
    }
  }

  async function handleRunReview() {
    setReviewLoading(true)
    try {
      await runResumeReview(token)
      await loadWorkspace()
    } catch (e) {
      setError(e.message)
    } finally {
      setReviewLoading(false)
    }
  }

  async function handleRunAnalysis(jobId = null) {
    const actualJobId = typeof jobId === 'string' ? jobId : null
    setAnalyzeLoading(true)
    try {
      await runResumeAnalysis(token, actualJobId)
      await loadWorkspace()
    } catch (e) {
      setError(e.message)
    } finally {
      setAnalyzeLoading(false)
    }
  }

  async function handleFetchCoherence(targetRole, regenerate = false) {
    setCoherenceLoading(true)
    setCoherenceError(null)
    try {
      const data = await getResumeCoherence(token, targetRole, regenerate)
      setCoherence(data)
    } catch (e) {
      setCoherenceError(e.message)
    } finally {
      setCoherenceLoading(false)
    }
  }

  async function handleFetchTailoring(jobId, regenerate = false) {
    setTailoringLoading(true)
    setTailoringError(null)
    try {
      const data = await getResumeTailoring(token, jobId, regenerate)
      setTailoring(data)
    } catch (e) {
      setTailoringError(e.message)
    } finally {
      setTailoringLoading(false)
    }
  }

  const hasResume = workspace?.has_resume
  const analysis = workspace?.latest_analysis
  const review = workspace?.latest_review
  const evidenceModule = analysis?.modules?.evidence

  return (
    <div className="resume-layout">
      {uploadLoading && (
        <div className="resume-upload-overlay">
          <div className="resume-upload-overlay__card">
            <div className="resume-spinner" />
            <span className="resume-upload-overlay__text">Uploading resume...</span>
          </div>
        </div>
      )}
      <Sidebar />
      <div className="resume-main">
        <TopBar section="Profile" page="Resume" />

        <div className="resume-content">

          {/* Page hero */}
          <div className="resume-hero">
            <div>
              <h1 className="resume-hero__title">Resume</h1>
              <p className="resume-hero__eyebrow">How are you presenting yourself to recruiters?</p>
            </div>
          </div>

          {/* Loading */}
          {loading && (
            <div className="resume-loading">
              <div className="resume-spinner" />
              <span>Loading resume workspace…</span>
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div className="resume-empty">
              <div className="resume-empty__icon" style={{ background: 'var(--danger-soft)', color: 'var(--danger)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              </div>
              <div className="resume-empty__title">Something went wrong</div>
              <div className="resume-empty__sub">{error}</div>
            </div>
          )}

          {/* Empty state — no resume */}
          {!loading && !error && !hasResume && (
            <div className="resume-empty">
              <div className="resume-empty__icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="12" y1="18" x2="12" y2="12" /><line x1="9" y1="15" x2="15" y2="15" />
                </svg>
              </div>
              <div className="resume-empty__title">No resume uploaded yet</div>
              <div className="resume-empty__sub">
                Upload your resume to unlock ATS checks, version history, skill analysis, and job matching.
              </div>
              <input
                ref={uploadInputRef}
                type="file"
                accept=".pdf,.docx"
                hidden
                onChange={(e) => handleUpload(e.target.files?.[0])}
              />
              <button
                className="resume-hero__btn resume-hero__btn--primary"
                onClick={() => uploadInputRef.current?.click()}
                disabled={uploadLoading}
              >
                {uploadLoading ? 'Uploading…' : 'Upload Resume'}
              </button>
            </div>
          )}

          {/* Main workspace */}
          {!loading && !error && hasResume && (
            <div className="resume-flow">
              <ResumeHeader
                workspace={workspace}
                onUpload={handleUpload}
                uploadLoading={uploadLoading}
                onReview={handleRunReview}
                reviewLoading={reviewLoading}
                onAnalyze={handleRunAnalysis}
                analyzeLoading={analyzeLoading}
                uploadInputRef={uploadInputRef}
                showPreview={showPreview}
                onTogglePreview={() => setShowPreview(!showPreview)}
              />

              {showPreview && (
                <ResumePdfViewer hasPdf={workspace.current_resume?.has_pdf} />
              )}

              {/* Tier 1 — the 15-second answer */}
              <ExecutiveSummary analysis={analysis} review={review} />

              <div id="priority-fixes">
                <PriorityFixes suggestions={analysis?.suggestions || []} />
              </div>

              {/* Tier 2 — improve & strengthen */}
              <ResumeReviewPanel
                review={review}
                onRunReview={handleRunReview}
                reviewLoading={reviewLoading}
              />

              <SkillsCoveragePanel
                profile_consistency={workspace.profile_consistency}
                evidence={evidenceModule}
                coverage_gaps={workspace.coverage_gaps}
              />

              <ResumeVsJobsPanel resume_vs_jobs={workspace.resume_vs_jobs} />

              {/* Tier 3 — advanced / on-demand intelligence */}
              <div className="resume-advanced">
                <ResumeAnalysisPanel
                  analysis={analysis}
                  onRunAnalysis={handleRunAnalysis}
                  analysisLoading={analyzeLoading}
                />

                <ResumeCoherence
                  token={token}
                  onFetch={handleFetchCoherence}
                  data={coherence}
                  loading={coherenceLoading}
                  error={coherenceError}
                />

                <ResumeTailoring
                  jobs={jobs}
                  onFetch={handleFetchTailoring}
                  data={tailoring}
                  loading={tailoringLoading}
                  error={tailoringError}
                />

                <ResumeEvolution evolution={evolution} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}