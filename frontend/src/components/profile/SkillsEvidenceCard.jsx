import { useState } from 'react'
import Card from '../common/Card'
import { IconTarget } from '../icons/Icons'
import { HiddenItems } from './evidence/ReviewControls'
import './ProfileSectionCard.css'
import './evidence/EvidenceReview.css'

const GROUPS = [
  { label: 'high', title: 'High confidence' },
  { label: 'medium', title: 'Medium confidence' },
  { label: 'low', title: 'Low confidence' },
]

function SkillRow({ skill, busy, onHide }) {
  const [open, setOpen] = useState(false)
  const sourceCount = skill.sources.length

  return (
    <div className="psc__skill-row" style={{ flexWrap: 'wrap' }}>
      <span className="psc__skill-name">{skill.skill}</span>
      <div className="psc__skill-meta">
        <span className={`psc__confidence psc__confidence--${skill.label}`}>
          {skill.label.charAt(0).toUpperCase() + skill.label.slice(1)}
        </span>
        <button type="button" className="evr__hidden-toggle" onClick={() => setOpen((v) => !v)}>
          {sourceCount} source{sourceCount === 1 ? '' : 's'} {open ? '▲' : '▾'}
        </button>
        <button type="button" className="evr__btn evr__btn--quiet" disabled={busy} onClick={() => onHide(skill)}>
          Hide
        </button>
      </div>
      {open && (
        <div style={{ width: '100%', fontSize: 12.5, color: 'var(--text-soft)', paddingTop: 6 }}>
          {skill.sources.map((s) => <div key={s}>{s}</div>)}
          {skill.confidence_flags.map((f) => <div key={f} style={{ color: 'var(--danger)' }}>{f}</div>)}
        </div>
      )}
    </div>
  )
}

function SkillsEvidenceCard({ skills = [], loading, onSetVisibility }) {
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const visible = skills.filter((s) => !s.is_hidden)
  const hidden = skills.filter((s) => s.is_hidden).map((s) => ({ ...s, id: s.skill }))

  async function setHidden(skill, isHidden) {
    setBusy(skill.skill)
    setError('')
    try {
      await onSetVisibility(skill.skill, isHidden)
    } catch (err) {
      setError(err.message || 'That change could not be saved.')
    } finally {
      setBusy(null)
    }
  }

  const hasLow = visible.some((s) => s.label === 'low')

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconTarget size={16} /></span>
          <h3 className="psc__title">Skills and evidence</h3>
          {visible.length > 0 && <span className="psc__count">{visible.length}</span>}
        </div>
      </div>

      {hasLow && (
        <div className="psc__skills-warning">
          <div className="psc__skills-warning-title">Needs more evidence</div>
          <div className="psc__skills-warning-body">
            Some skills have low confidence — add outcomes, a project, or a source connection rather than editing a score.
          </div>
        </div>
      )}

      {error && <p className="psc__error">{error}</p>}

      {loading ? (
        <div className="psc__empty"><span className="psc__empty-text">Loading…</span></div>
      ) : visible.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No skills detected yet — upload a resume or sync a source to get started.</span>
        </div>
      ) : (
        GROUPS.map((group) => {
          const rows = visible.filter((s) => s.label === group.label)
          if (!rows.length) return null
          return (
            <div key={group.label} className="psc__skill-group">
              <div className="psc__skill-group-label">{group.title}</div>
              {rows.map((s) => (
                <SkillRow key={s.skill} skill={s} busy={busy === s.skill} onHide={(sk) => setHidden(sk, true)} />
              ))}
            </div>
          )
        })
      )}

      <HiddenItems
        label="skill"
        items={hidden}
        nameOf={(s) => s.skill}
        busyId={busy}
        onRestore={(s) => setHidden(s, false)}
      />
    </Card>
  )
}

export default SkillsEvidenceCard
