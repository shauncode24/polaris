import { useRef, useState } from 'react'
import Button from '../common/Button'
import './JobDescriptionForm.css'

const MODES = [
  { key: 'text', label: 'Paste Text' },
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
    <form className="jd-form" onSubmit={handleSubmit}>
      <div className="jd-form__mode-toggle" role="tablist">
        {MODES.map((m) => (
          <button
            key={m.key}
            type="button"
            role="tab"
            aria-selected={mode === m.key}
            className={`jd-form__mode-btn ${mode === m.key ? 'jd-form__mode-btn--active' : ''}`}
            onClick={() => setMode(m.key)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {mode === 'text' ? (
        <textarea
          className="jd-form__textarea"
          rows={12}
          placeholder="Paste the full job description here..."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
      ) : (
        <div>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf"
            hidden
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          <div
            className="jd-form__dropzone"
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            {file ? (
              <p>{file.name} <span className="jd-form__browse">Change file</span></p>
            ) : (
              <p>Drop a PDF job description here, or <span className="jd-form__browse">browse</span></p>
            )}
          </div>
        </div>
      )}

      <div className="jd-form__row">
        <label>
          Company <span className="jd-form__optional">(optional)</span>
          <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Acme Corp" />
        </label>
        <label>
          Role <span className="jd-form__optional">(optional)</span>
          <input type="text" value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Backend Engineer" />
        </label>
      </div>

      {formError && <p className="jd-form__error">{formError}</p>}

      <Button type="submit" variant="primary" disabled={loading}>
        {loading ? 'Analyzing…' : 'Analyze →'}
      </Button>
    </form>
  )
}

export default JobDescriptionForm