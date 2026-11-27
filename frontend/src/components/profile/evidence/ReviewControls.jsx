import { useState } from 'react'
import './EvidenceReview.css'

const SOURCE_LABELS = {
  resume: 'Resume', github: 'GitHub', linkedin: 'LinkedIn', leetcode: 'LeetCode', certificate: 'Certificate',
}

// Where an item came from. Every item in the evidence record shows this.
export function SourceBadges({ sources = [] }) {
  return (
    <span className="evr__sources">
      {sources.map((s) => (
        <span key={s} className={`evr__source evr__source--${s}`}>{SOURCE_LABELS[s] || s}</span>
      ))}
    </span>
  )
}

export function ReviewBadge({ item }) {
  if (item.is_hidden) return <span className="evr__state evr__state--hidden">Hidden</span>
  if (item.review_state === 'edited') return <span className="evr__state">Edited by you</span>
  if (item.review_state === 'confirmed') return <span className="evr__state evr__state--confirmed">Confirmed</span>
  return null
}

// Confirm / Edit / Hide (or Restore) for one item.
export function ReviewActions({ item, busy, onConfirm, onEdit, onHide, onRestore }) {
  if (item.is_hidden) {
    return (
      <div className="evr__actions">
        <button type="button" className="evr__btn" disabled={busy} onClick={onRestore}>Restore</button>
      </div>
    )
  }
  return (
    <div className="evr__actions">
      {item.review_state === 'auto' && (
        <button type="button" className="evr__btn" disabled={busy} onClick={onConfirm}>Confirm</button>
      )}
      <button type="button" className="evr__btn" disabled={busy} onClick={onEdit}>Edit</button>
      <button type="button" className="evr__btn evr__btn--quiet" disabled={busy} onClick={onHide}>Hide</button>
    </div>
  )
}

// Items the user hid: kept out of everything else, listed here so they can be restored.
export function HiddenItems({ label, items, nameOf, busyId, onRestore }) {
  const [open, setOpen] = useState(false)
  if (!items.length) return null
  return (
    <div className="evr__hidden-section">
      <button type="button" className="evr__hidden-toggle" onClick={() => setOpen((v) => !v)}>
        {items.length} hidden {label}{items.length === 1 ? '' : 's'} {open ? '▲' : '▾'}
      </button>
      {open && (
        <div className="evr__hidden-list">
          {items.map((item) => (
            <div key={item.id || nameOf(item)} className="evr__hidden-row">
              <span>{nameOf(item)}</span>
              <button type="button" className="evr__btn" disabled={busyId === (item.id || nameOf(item))}
                onClick={() => onRestore(item)}>Restore</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// fields: [{ name, label, kind: 'text' | 'textarea' | 'comma' | 'lines' }]
// 'comma' / 'lines' edit a list as comma-separated text / one entry per line.
function toText(kind, value) {
  if (kind === 'comma') return (value || []).join(', ')
  if (kind === 'lines') return (value || []).join('\n')
  return value ?? ''
}

function fromText(kind, text) {
  if (kind === 'comma') return text.split(',').map((v) => v.trim()).filter(Boolean)
  if (kind === 'lines') return text.split('\n').map((v) => v.trim()).filter(Boolean)
  return text
}

export function EditForm({ fields, initial, saving, error, onSave, onCancel }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(fields.map((f) => [f.name, toText(f.kind, initial[f.name])]))
  )

  function submit(event) {
    event.preventDefault()
    onSave(Object.fromEntries(fields.map((f) => [f.name, fromText(f.kind, values[f.name])])))
  }

  return (
    <form className="evr__form" onSubmit={submit}>
      {fields.map((f) => (
        <label key={f.name} className="evr__field">
          <span>{f.label}</span>
          {f.kind === 'text' || f.kind === 'comma' ? (
            <input
              value={values[f.name]}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
              disabled={saving}
            />
          ) : (
            <textarea
              rows={f.kind === 'lines' ? 5 : 3}
              value={values[f.name]}
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })}
              disabled={saving}
            />
          )}
        </label>
      ))}
      {error && <p className="evr__error">{error}</p>}
      <div className="evr__actions">
        <button type="submit" className="evr__btn evr__btn--primary" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button type="button" className="evr__btn" disabled={saving} onClick={onCancel}>Cancel</button>
      </div>
    </form>
  )
}
