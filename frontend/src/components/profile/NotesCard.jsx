import { useState } from 'react'
import Card from '../common/Card'
import './ProfileSectionCard.css'

function NotesCard() {
  const [notes, setNotes] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [text, setText] = useState('')

  function handleAdd() {
    if (!text.trim()) return
    setNotes((prev) => [
      ...prev,
      { id: crypto.randomUUID(), text: text.trim(), date: new Date().toLocaleDateString() },
    ])
    setText('')
    setShowForm(false)
  }

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <rect x="5.5" y="4.5" width="13" height="16" rx="1.5" />
              <path d="M9 4.5V3.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M9 11h6M9 14.5h6M9 8h3" />
            </svg>
          </span>
          <h3 className="psc__title">Notes and learning log</h3>
        </div>
        <button type="button" className="psc__add-btn" onClick={() => setShowForm((v) => !v)}>
          <span>+</span> Add note
        </button>
      </div>

      {showForm && (
        <div className="psc__body">
          <textarea
            className="notes__textarea"
            placeholder="What did you learn or ship today?"
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="psc__text-btn" onClick={() => setShowForm(false)}>Cancel</button>
            <button
              type="button"
              className="cert-form__submit"
              disabled={!text.trim()}
              onClick={handleAdd}
            >
              Save note
            </button>
          </div>
        </div>
      )}

      {notes.length === 0 && !showForm ? (
        <div className="psc__notes-empty">
          No notes yet — capture a small reflection after you learn or ship something.
        </div>
      ) : (
        notes.map((n) => (
          <div key={n.id} className="psc__item">
            <div className="psc__item-sub" style={{ marginBottom: 4 }}>{n.date}</div>
            <div className="psc__item-desc">{n.text}</div>
          </div>
        ))
      )}
    </Card>
  )
}

export default NotesCard
