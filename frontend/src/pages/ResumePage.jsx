import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { getResumeWorkspace, uploadResume, runResumeReview } from '../api/resume'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ResumeHeader from '../components/resume/ResumeHeader'
import ResumePdfViewer from '../components/resume/ResumePdfViewer'
import ResumeSnapshot from '../components/resume/ResumeSnapshot'
import ResumeHealth from '../components/resume/ResumeHealth'
import ResumeReviewPanel from '../components/resume/ResumeReviewPanel'
import ResumeVersions from '../components/resume/ResumeVersions'
import ResumeConsistency from '../components/resume/ResumeConsistency'
import ResumeVsJobs from '../components/resume/ResumeVsJobs'
import ResumeEvolution from '../components/resume/ResumeEvolution'
import './ResumePage.css'

export default function ResumePage() {
  const { token } = useAuth()
  const uploadInputRef = useRef(null)

  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [error, setError] = useState(null)

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

  useEffect(() => {
    loadWorkspace()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function handleUpload(file) {
    if (!file) return
    setUploadLoading(true)
    try {
      await uploadResume(file, token)
      // Reload workspace after upload
      setLoading(true)
      await loadWorkspace()
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
      // Reload workspace to pull the new review
      await loadWorkspace()
    } catch (e) {
      setError(e.message)
    } finally {
      setReviewLoading(false)
    }
  }

  const hasResume = workspace?.has_resume

  return (
    <div className="resume-layout">
      <Sidebar />
      <div className="resume-main">
        <TopBar section="Profile" page="Resume" />

        <div className="resume-content">

          {/* Page hero */}
          <div className="resume-hero">
            <div>
              <p className="resume-hero__eyebrow">How are you presenting yourself to recruiters?</p>
              <h1 className="resume-hero__title">Resume</h1>
              {hasResume && (
                <div className="resume-hero__meta">
                  <span>Your resume workspace</span>
                  <span className="resume-hero__meta-dot" />
                  <span>{workspace.versions?.length || 1} version{workspace.versions?.length !== 1 ? 's' : ''} on record</span>
                </div>
              )}
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
            <>
              <ResumeHeader
                workspace={workspace}
                onUpload={handleUpload}
                onReview={handleRunReview}
                reviewLoading={reviewLoading}
                uploadInputRef={uploadInputRef}
              />

              <div className="resume-columns">
                {/* Left column */}
                <div className="resume-col">
                  <ResumePdfViewer hasPdf={workspace.current_resume?.has_pdf} />
                  <ResumeSnapshot snapshot={workspace.snapshot} />
                  <ResumeHealth ats_flags={workspace.ats_flags} />
                  <ResumeReviewPanel
                    review={workspace.latest_review}
                    onRunReview={handleRunReview}
                    reviewLoading={reviewLoading}
                  />
                </div>

                {/* Right column */}
                <div className="resume-col">
                  <ResumeVersions versions={workspace.versions} />
                  <ResumeConsistency profile_consistency={workspace.profile_consistency} />
                  <ResumeVsJobs resume_vs_jobs={workspace.resume_vs_jobs} />
                  <ResumeEvolution />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
