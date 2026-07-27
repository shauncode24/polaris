import { useRef, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { uploadResume } from '../../api/profile'
import { IconDocument } from '../icons/Icons'
import { IconTrash } from '../icons/OnboardingIcons'
import Card from '../common/Card'
import './ProfileSectionCard.css'

function ResumeCard({ result, onSuccess }) {
  const { token } = useAuth()
  const inputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(file) {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      const data = await uploadResume(file, token)
      onSuccess({ ...data, filename: file.name })
    } catch (err) {
      setError(err.message || 'Could not process this resume.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <Card className="psc">
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        hidden
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconDocument size={16} /></span>
          <h3 className="psc__title">Resume</h3>
        </div>
        <div className="psc__header-actions">
          {result && (
            <button type="button" className="psc__text-btn">History</button>
          )}
          <button
            type="button"
            className="psc__text-btn"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Uploading…' : 'Re-upload'}
          </button>
        </div>
      </div>

      {error && <p className="psc__error">{error}</p>}

      {!result && !uploading && (
        <div
          className="psc__dropzone"
          onClick={() => inputRef.current?.click()}
        >
          <span className="psc__dropzone-text">Drop your resume here or <span className="psc__link">browse files</span></span>
          <span className="psc__dropzone-sub">PDF or DOCX · up to 10 MB</span>
        </div>
      )}

      {result && (
        <>
          <div className="psc__file-row">
            <div className="psc__file-info">
              <span className="psc__file-name">{result.filename || 'resume.pdf'}</span>
              <span className="psc__file-sub">Uploaded during your latest profile snapshot</span>
            </div>
            <span className="psc__badge psc__badge--success">Current version</span>
          </div>

          <button type="button" className="psc__link-action">▶ View extracted profile data</button>

          <div className="psc__footer-row">
            <span className="psc__muted">No review run yet.</span>
            <button type="button" className="psc__link-action psc__link-action--accent">Run a review →</button>
          </div>
        </>
      )}

      {uploading && (
        <div className="psc__loading">Processing your resume…</div>
      )}
    </Card>
  )
}

export default ResumeCard
