import { useRef, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { uploadResume } from '../../api/profile'
import './ProfileIngestion.css'

function ResumeUploadCard({ result, onSuccess }) {
  const { token } = useAuth()
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  async function handleFile(file) {
    if (!file) return
    setFileName(file.name)
    setUploading(true)
    setError('')
    try {
      const data = await uploadResume(file, token)
      onSuccess(data)
    } catch (err) {
      setError(err.message || 'Could not process this resume. Make sure it is a text-based PDF.')
    } finally {
      setUploading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    handleFile(e.dataTransfer.files?.[0])
  }

  return (
    <div className={`ingest-card ${result ? 'ingest-card--done' : ''}`}>
      <div className="ingest-card__header">
        <h3>Resume</h3>
        {result && <span className="ingest-card__badge">✓ Uploaded</span>}
      </div>
      <input ref={inputRef} type="file" accept=".pdf" hidden onChange={(e) => handleFile(e.target.files?.[0])} />
      {error && <p className="ingest-card__error">{error}</p>}
      {!result ? (
        <div className="ingest-card__dropzone" onDragOver={(e) => e.preventDefault()} onDrop={handleDrop} onClick={() => inputRef.current?.click()}>
          {uploading ? <p>Uploading {fileName}…</p> : <p>Drop your PDF resume here, or <span className="ingest-card__browse">browse</span></p>}
        </div>
      ) : (
        <div className="ingest-card__stats">
          <span>{result.skills_processed} skills</span>
          <span>{result.projects_created} projects</span>
          <span>{result.experiences_created} experiences</span>
          <span>{result.education_created} education entries</span>
          <button type="button" className="ingest-card__reset" onClick={() => inputRef.current?.click()} disabled={uploading}>
            {uploading ? 'Uploading…' : 'Re-upload'}
          </button>
        </div>
      )}
    </div>
  )
}

export default ResumeUploadCard