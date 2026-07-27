import { useState } from 'react'
import Card from '../common/Card'
import { IconAward, IconTrash } from '../icons/OnboardingIcons'
import './ProfileSectionCard.css'

function CertificatesCard({ certificates, onChange }) {
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [issuer, setIssuer] = useState('')
  const [date, setDate] = useState('')

  function handleAdd() {
    if (!name.trim() || !issuer.trim()) return
    const next = [...certificates, { id: crypto.randomUUID(), name: name.trim(), issuer: issuer.trim(), date }]
    onChange(next)
    setName(''); setIssuer(''); setDate('')
    setShowForm(false)
  }

  function handleRemove(id) {
    onChange(certificates.filter((c) => c.id !== id))
  }

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconAward size={16} /></span>
          <h3 className="psc__title">Certificates</h3>
        </div>
        <button type="button" className="psc__add-btn" onClick={() => setShowForm((v) => !v)}>
          <span>+</span> Add
        </button>
      </div>

      {showForm && (
        <div className="psc__body">
          <div className="cert-form">
            <input
              className="cert-form__input"
              placeholder="Certificate name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <input
              className="cert-form__input"
              placeholder="Issuer"
              value={issuer}
              onChange={(e) => setIssuer(e.target.value)}
            />
            <input
              className="cert-form__input"
              placeholder="Date earned (e.g. Mar 2024)"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <div className="cert-form__actions">
              <button type="button" className="psc__text-btn" onClick={() => setShowForm(false)}>Cancel</button>
              <button
                type="button"
                className="cert-form__submit"
                disabled={!name.trim() || !issuer.trim()}
                onClick={handleAdd}
              >
                Add certificate
              </button>
            </div>
          </div>
        </div>
      )}

      {certificates.length === 0 && !showForm ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No certificates yet.</span>
          <button type="button" className="psc__empty-cta" onClick={() => setShowForm(true)}>
            Add certificate →
          </button>
        </div>
      ) : (
        certificates.map((c) => (
          <div key={c.id} className="psc__item">
            <div className="psc__item-header">
              <div>
                <div className="psc__item-title">{c.name}</div>
                <div className="psc__item-sub">{c.issuer}{c.date ? ` · ${c.date}` : ''}</div>
              </div>
              <button
                type="button"
                className="psc__item-action-btn psc__item-action-btn--danger"
                onClick={() => handleRemove(c.id)}
                aria-label="Remove certificate"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                  <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
                </svg>
              </button>
            </div>
          </div>
        ))
      )}
    </Card>
  )
}

export default CertificatesCard
