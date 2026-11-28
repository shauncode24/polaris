import { useState } from 'react'

function linkedinOf(header) {
  return header.links.find((link) => link.label === 'LinkedIn')?.url ?? ''
}

// The name and contact details at the top. The phone number and LinkedIn link
// can be changed; `onChange` saves them and resolves to whether it worked.
export default function ContactHeader({ header, busy, error, onChange }) {
  const [draft, setDraft] = useState(null) // the form's values while open
  const details = [header.email, header.phone, header.location].filter(Boolean)

  const open = () => setDraft({ phone: header.phone ?? '', linkedin_url: linkedinOf(header) })
  const set = (field) => (event) => setDraft({ ...draft, [field]: event.target.value })

  async function save(event) {
    event.preventDefault()
    // Only what was changed, so an untouched field can't overwrite anything.
    const changed = {}
    if (draft.phone !== (header.phone ?? '')) changed.phone = draft.phone
    if (draft.linkedin_url !== linkedinOf(header)) changed.linkedin_url = draft.linkedin_url
    if (Object.keys(changed).length === 0 || await onChange(changed)) setDraft(null)
  }

  return (
    <header className="tr-contact">
      <h2>{header.full_name}</h2>
      <p>
        {details.join(' · ')}
        {header.links.map((link) => (
          <span key={link.url}> · <a href={link.url} target="_blank" rel="noreferrer">{link.label}</a></span>
        ))}
      </p>

      {draft === null ? (
        <div className="tr-links">
          <button type="button" onClick={open}>Edit contact details</button>
        </div>
      ) : (
        <form className="tr-contact__form" onSubmit={save}>
          <label>
            <span className="tr-label">Phone</span>
            <input type="tel" autoComplete="tel" maxLength={40} value={draft.phone} onChange={set('phone')} autoFocus />
          </label>
          <label>
            <span className="tr-label">LinkedIn profile</span>
            <input
              type="text"
              placeholder="linkedin.com/in/your-name"
              maxLength={200}
              value={draft.linkedin_url}
              onChange={set('linkedin_url')}
            />
          </label>
          {error && <p className="tr-line__error" role="alert">{error}</p>}
          <p className="tr-hint">Saved to this version and used for the ones you generate next.</p>
          <div className="tr-actions">
            <button type="submit" className="tr-btn tr-btn--primary" disabled={busy}>Save contact details</button>
            <button type="button" className="tr-btn" disabled={busy} onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </form>
      )}
    </header>
  )
}
