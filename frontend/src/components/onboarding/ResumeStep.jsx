import { useRef, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { uploadResume } from '../../api/profile'
import { IconCloudUpload } from '../icons/OnboardingIcons'
import { IconDocument } from '../icons/Icons'
import SimulatedProgressList from './SimulatedProgressList'
import StepFooterNav from './StepFooterNav'
import Button from '../common/Button'
import './onboarding-shared.css'

const PIPELINE_STEPS = [
  'Reading document',
  'Extracting experience & projects',
  'Detecting skills',
  'Scoring confidence',
]

function ResumeStep({ result, onSuccess, onContinue, onSkip }) {
  const { token } = useAuth()
  const inputRef = useRef(null)
  const [fileName, setFileName] = useState(result?.filename || '')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [dragOver, setDragOver] = useState(false)

  async function handleFile(file) {
    if (!file) return
    setFileName(file.name)
    setUploading(true)
    setError('')
    try {
      const data = await uploadResume(file, token)
      onSuccess({ ...data, filename: file.name })
    } catch (err) {
      setError(err.message || 'Could not process this resume. Make sure it is a text-based PDF.')
    } finally {
      setUploading(false)
    }
  }

  function handleDrop(e) {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files?.[0])
  }

  return (
    <div>
      <p className="onb-eyebrow">Step 1 of 6 · Resume</p>
      <h1 className="onb-title">Upload your resume</h1>
      <p className="onb-lead">
        This is the one thing we need to get started — it seeds your experience, projects, and skills.
        Everything after this is optional.
      </p>

      {error && <p className="onb-error">{error}</p>}

      <div className="onb-card">
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          hidden
          onChange={(e) => handleFile(e.target.files?.[0])}
        />

        {!result && !uploading && (
          <div
            className={`onb-dropzone ${dragOver ? 'onb-dropzone--drag' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <span className="onb-dropzone__icon-wrap"><IconCloudUpload size={22} /></span>
            <span className="onb-dropzone__title">Drop your resume here, or browse</span>
            <span className="onb-dropzone__sub">PDF or DOCX, up to 10 MB</span>
            <Button variant="primary" size="sm" onClick={(e) => { e.stopPropagation(); inputRef.current?.click() }}>
              Browse files
            </Button>
          </div>
        )}

        {uploading && (
          <div className="onb-file-row" style={{ marginBottom: 20 }}>
            <span className="onb-file-icon"><IconDocument size={18} /></span>
            <div>
              <div className="onb-file-name">{fileName}</div>
              <div className="onb-file-sub">Extracting your profile…</div>
            </div>
          </div>
        )}

        {uploading && <SimulatedProgressList steps={PIPELINE_STEPS} running={uploading} />}

        {result && !uploading && (
          <div className="onb-file-row" style={{ justifyContent: 'space-between' }}>
            <div className="onb-file-row">
              <span className="onb-file-icon onb-file-icon--done">✓</span>
              <div>
                <div className="onb-file-name">{result.filename}</div>
                <div className="onb-mini-bars">
                  <span className="onb-mini-bar onb-mini-bar--a" title={`${result.experiences_created} experiences`} />
                  <span className="onb-mini-bar onb-mini-bar--b" title={`${result.projects_created} projects`} />
                  <span className="onb-mini-bar onb-mini-bar--c" title={`${result.skills_processed} skills`} />
                </div>
              </div>
            </div>
            <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
              Re-upload
            </Button>
          </div>
        )}
      </div>

      {!result ? (
        <p className="onb-hint" style={{ textAlign: 'center', marginTop: 16 }}>
          A successful upload is required before you can continue.
        </p>
      ) : (
        <div className="onb-footer" style={{ justifyContent: 'flex-end' }}>
          <Button variant="primary" onClick={onContinue}>Looks good, continue →</Button>
        </div>
      )}
    </div>
  )
}

export default ResumeStep