import { useState } from 'react'
import { IconAward, IconTrash } from '../icons/OnboardingIcons'
import StepFooterNav from './StepFooterNav'
import './onboarding-shared.css'

function CertificatesStep({ certificates, onChange, onContinue, onSkip }) {
  const [name, setName] = useState('')
  const [issuer, setIssuer] = useState('')
  const [date, setDate] = useState('')
  const [skills, setSkills] = useState('')

  const canAdd = name.trim() && issuer.trim()

  function handleAdd() {
    if (!canAdd) return
    onChange([...certificates, { id: crypto.randomUUID(), name: name.trim(), issuer: issuer.trim(), date, skills }])
    setName(''); setIssuer(''); setDate(''); setSkills('')
  }

  function handleRemove(id) {
    onChange(certificates.filter((c) => c.id !== id))
  }

  return (
    <div>
      <p className="onb-eyebrow">Step 4 of 6 · Certificates</p>
      <h1 className="onb-title">Add any certificates</h1>
      <p className="onb-lead">
        Optional, and lower priority — you can always add these later. They add extra proof to your
        profile when they're relevant to your target role.
      </p>

      {certificates.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
          {certificates.map((c) => (
            <div key={c.id} className="onb-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px' }}>
              <div className="onb-file-row">
                <span className="onb-file-icon"><IconAward size={16} /></span>
                <div>
                  <div className="onb-file-name">{c.name}</div>
                  <div className="onb-file-sub">{c.issuer}{c.date ? ` · ${c.date}` : ''}</div>
                </div>
              </div>
              <button type="button" className="onb-link-btn" style={{ color: 'var(--text-soft)' }} onClick={() => handleRemove(c.id)}>
                <IconTrash size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="onb-card">
        <div className="onb-row">
          <div className="onb-field">
            <label>Certificate name</label>
            <input className="onb-input" placeholder="AWS Solutions Architect" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="onb-field">
            <label>Issuer</label>
            <input className="onb-input" placeholder="Amazon Web Services" value={issuer} onChange={(e) => setIssuer(e.target.value)} />
          </div>
        </div>
        <div className="onb-row">
          <div className="onb-field">
            <label>Date earned <span className="onb-optional">Optional</span></label>
            <input className="onb-input" placeholder="Mar 2024" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div className="onb-field">
            <label>Related skills <span className="onb-optional">Optional</span></label>
            <input className="onb-input" placeholder="Cloud, DevOps" value={skills} onChange={(e) => setSkills(e.target.value)} />
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 4 }}>
          <button type="button" className="onb-link-btn" disabled title="File-based certificate parsing isn't built yet">
            ⬆ Upload file instead
          </button>
          <button
            type="button"
            className="btn btn--primary btn--sm"
            disabled={!canAdd}
            onClick={handleAdd}
          >
            + Add certificate
          </button>
        </div>
      </div>

      <StepFooterNav skipLabel="Skip / add later" onSkip={onSkip} continueLabel="Continue" onContinue={onContinue} />
    </div>
  )
}

export default CertificatesStep