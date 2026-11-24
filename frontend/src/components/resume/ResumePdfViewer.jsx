import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { fetchResumePdf } from '../../api/resume'
import CollapsibleSection from '../common/CollapsibleSection'
import './ResumePdfViewer.css'

export default function ResumePdfViewer({ hasPdf }) {
  const { token } = useAuth()
  const [pdfUrl, setPdfUrl] = useState(null)
  const [loading, setLoading] = useState(false)

  // An <embed> can't send an Authorization header, so fetch the PDF with the
  // header and show it from a temporary object URL instead of putting the
  // token in the URL.
  useEffect(() => {
    if (!hasPdf) {
      setPdfUrl(null)
      return undefined
    }
    let cancelled = false
    let objectUrl = null
    setLoading(true)
    fetchResumePdf(token)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setPdfUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setPdfUrl(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [hasPdf, token])

  const actions = pdfUrl ? (
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
    <div className="rpv-panel">
      <div className="rpv-panel__header">
        <span className="rpv-panel__title">Resume PDF Preview</span>
        {actions}
      </div>
      <div className="rpv__embed-wrap">
        {pdfUrl ? (
          <embed
            src={pdfUrl}
            type="application/pdf"
            className="rpv__embed"
          />
        ) : loading ? (
          <div className="rpv__no-pdf">
            <p>Loading preview…</p>
          </div>
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
    </div>
  )
}
