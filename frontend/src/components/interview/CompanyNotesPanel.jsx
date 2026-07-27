// frontend/src/components/interview/CompanyNotesPanel.jsx
import { useState } from 'react'
import './CompanyNotesPanel.css'

function formatWhen(iso) {
  const date = new Date(iso)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return 'Today'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function CompanyNotesPanel({ company, notes, loading, onAdd }) {
  const [showForm, setShowForm] = useState(false)
  const [text, setText] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    if (!text.trim() || !company) return
    setSaving(true)
    try {
      await onAdd(text.trim())
      setText('')
      setShowForm(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="company-notes">
      <div className="company-notes__header">
        <div>
          <h3>Company notes</h3>
          <p className="company-notes__lead">Context that sharpens coaching</p>
        </div>
        <button
          type="button"
          className="company-notes__add-btn"
          onClick={() => setShowForm((v) => !v)}
          disabled={!company}
          title={company ? 'Add a note' : 'Set a target company first'}
        >
          +
        </button>
      </div>

      {showForm && (
        <div className="company-notes__form">
          <textarea
            rows={3}
            placeholder={`Paste anything useful about ${company}…`}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="company-notes__form-actions">
            <button type="button" className="company-notes__cancel" onClick={() => setShowForm(false)}>Cancel</button>
            <button type="button" className="company-notes__save" disabled={!text.trim() || saving} onClick={handleSave}>
              {saving ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </div>
      )}

      {!company ? (
        <p className="company-notes__empty">Set a target company to attach notes here.</p>
      ) : loading ? (
        <p className="company-notes__empty">Loading…</p>
      ) : notes.length === 0 ? (
        <p className="company-notes__empty">No notes yet for {company}.</p>
      ) : (
        <div className="company-notes__list">
          {notes.map((n) => (
            <div key={n.id} className="company-notes__card">
              <div className="company-notes__card-header">
                <span className="company-notes__card-title">{n.company}</span>
                <span className="company-notes__card-date">{formatWhen(n.created_at)}</span>
              </div>
              <p className="company-notes__card-body">{n.pasted_content}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default CompanyNotesPanel