// frontend/src/components/leetcode/ManualEntryModal.jsx
import { useState } from 'react'
import './ManualEntryModal.css'

function parseTagLine(line) {
  const [tag, count] = line.split(':').map((s) => s.trim())
  return tag && count && !Number.isNaN(Number(count)) ? [tag, Number(count)] : null
}

function ManualEntryModal({ onClose, onSubmit }) {
  const [text, setText] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  async function handleSubmit() {
    const tagCounts = {}
    for (const line of text.split('\n')) {
      if (!line.trim()) continue
      const parsed = parseTagLine(line)
      if (!parsed) {
        setError(`Couldn't parse "${line}" — use "tag-slug: count".`)
        return
      }
      tagCounts[parsed[0]] = parsed[1]
    }
    if (Object.keys(tagCounts).length === 0) {
      setError('Add at least one line, e.g. "dynamic-programming: 42".')
      return
    }
    setSaving(true)
    setError('')
    try {
      await onSubmit(tagCounts)
    } catch (err) {
      setError(err.message || 'Could not save your manual submission.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="lc-modal__backdrop" onClick={onClose}>
      <div className="lc-modal" onClick={(e) => e.stopPropagation()}>
        <h3>Manual entry</h3>
        <p className="lc-modal__lead">
          Enter tag counts manually, one per line, as <code>tag-slug: count</code>.
        </p>
        <textarea
          className="lc-modal__textarea"
          rows={6}
          placeholder={'dynamic-programming: 42\narray: 88'}
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        {error && <p className="lc-modal__error">{error}</p>}
        <div className="lc-modal__actions">
          <button type="button" className="lc-modal__cancel" onClick={onClose}>Cancel</button>
          <button type="button" className="lc-modal__save" onClick={handleSubmit} disabled={saving}>
            {saving ? 'Saving…' : 'Save counts'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ManualEntryModal