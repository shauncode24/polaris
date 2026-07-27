import { useRef, useState } from 'react'
import Button from '../common/Button'
import { IconCloudUpload } from '../icons/OnboardingIcons'
import { IconArrowRight } from '../icons/Icons'
import './JobDescriptionForm.css'

const MODES = [
  { key: 'text', label: 'Paste text' },
  { key: 'pdf', label: 'Upload PDF' },
]

function JobDescriptionForm({ onSubmit, loading }) {
  const [mode, setMode] = useState('text')
  const [text, setText] = useState('')
  const [file, setFile] = useState(null)
  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [formError, setFormError] = useState('')
  const inputRef = useRef(null)

  function handleFile(f) {
    if (!f) return
    if (f.type !== 'application/pdf') {
      setFormError('Please choose a PDF file.')
      return
    }
    setFormError('')
    setFile(f)
  }

  function handleDrop(e) {
    e.preventDefault()
    handleFile(e.dataTransfer.files?.[0])
  }

  function handleSubmit(e) {
    e.preventDefault()
    setFormError('')

    if (mode === 'text') {
      if (!text.trim()) {
        setFormError('Paste a job description first.')
        return
      }
      onSubmit({ mode, text, company: company.trim(), role: role.trim() })
    } else {
      if (!file) {
        setFormError('Choose a PDF to upload.')
        return
      }
      onSubmit({ mode, file, company: company.trim(), role: role.trim() })
    }
  }

  return (
    <form className="jd-form-card" onSubmit={handleSubmit}>
      <div className="jd-form-card__header">
        <h3>New analysis</h3>
        <div className="jd-form-card__tabs" role="tablist">
          {MODES.map((m) => (
            <button
              key={m.key}
              type="button"
              role="tab"
              aria-selected={mode === m.key}
              className={`jd-form-card__tab ${mode === m.key ? 'jd-form-card__tab--active' : ''}`}
              onClick={() => setMode(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {mode === 'text' ? (
        <label className="jd-form-card__field">
          <span>Job description</span>
          <textarea
            className="jd-form-card__textarea"
            rows={10}
            placeholder="Paste the full job description here…"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </label>
      ) : (
        <div className="jd-form-card__field">
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <div
            className="jd-form-card__dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <span className="jd-form-card__dropzone-icon"><IconCloudUpload size={22} /></span>
            {file ? (
              <>
                <span className="jd-form-card__dropzone-title">{file.name}</span>
                <span className="jd-form-card__dropzone-sub">Click to choose a different file</span>
              </>
            ) : (
              <>
                <span className="jd-form-card__dropzone-title">Drop a PDF here, or click to browse</span>
                <span className="jd-form-card__dropzone-sub">We'll extract the role and company for you</span>
              </>
            )}
          </div>
        </div>
      )}

      <div className="jd-form-card__row">
        <label className="jd-form-card__field">
          <span>Company <em>optional</em></span>
          <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Auto-filled if left blank" />
        </label>
        <label className="jd-form-card__field">
          <span>Role <em>optional</em></span>
          <input type="text" value={role} onChange={(e) => setRole(e.target.value)} placeholder="Auto-filled if left blank" />
        </label>
      </div>

      {formError && <p className="jd-form-card__error">{formError}</p>}

      <div className="jd-form-card__footer">
        <Button type="submit" variant="primary" disabled={loading} icon={!loading ? <IconArrowRight size={16} /> : null}>
          {loading ? 'Analyzing…' : 'Analyze'}
        </Button>
      </div>
    </form>
  )
}

export default JobDescriptionForm