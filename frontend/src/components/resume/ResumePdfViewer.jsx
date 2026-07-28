import { useAuth } from '../../contexts/AuthContext'
import { getResumeDownloadUrl } from '../../api/resume'
import CollapsibleSection from '../common/CollapsibleSection'
import './ResumePdfViewer.css'

export default function ResumePdfViewer({ hasPdf }) {
  const { token } = useAuth()

  // Build a URL that includes the auth token as a query param so the
  // <embed> tag (which can't set custom headers) can still authenticate.
  // The backend reads ?token=... as a fallback on this endpoint.
  const pdfUrl = hasPdf
    ? `${getResumeDownloadUrl()}?token=${encodeURIComponent(token || '')}`
    : null

  const actions = hasPdf ? (
    <div className="rpv__actions">
      <a
        href={pdfUrl}
        download
        className="rpv__btn"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 4v12M7.5 14.5L12 19l4.5-4.5" />
          <path d="M4 19v2a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-2" />
        </svg>
        Download
      </a>
    </div>
  ) : null

  return (
    <CollapsibleSection title="Resume Preview" defaultOpen={false} actions={actions} className="rpv">
      <div className="rpv__embed-wrap">
        {hasPdf ? (
          <embed
            src={pdfUrl}
            type="application/pdf"
            className="rpv__embed"
          />
        ) : (
          <div className="rpv__no-pdf">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
            <p>PDF preview not available.</p>
            <p style={{ fontSize: 12, color: 'var(--text-soft)' }}>
              Re-upload your resume to enable inline preview.
            </p>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}
