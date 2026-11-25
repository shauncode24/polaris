import Card from '../common/Card'
import {
  EditForm, HiddenItems, ReviewActions, ReviewBadge, SourceBadges,
} from './evidence/ReviewControls'
import { useReviewActions } from './evidence/useReviewActions'
import './ProfileSectionCard.css'
import './evidence/EvidenceReview.css'

const EDIT_FIELDS = [
  { name: 'role', label: 'Role', kind: 'text' },
  { name: 'company', label: 'Company', kind: 'text' },
  { name: 'stack', label: 'Technologies (comma separated)', kind: 'comma' },
  { name: 'bullets', label: 'Highlights (one per line)', kind: 'lines' },
]

function ExperienceItem({ exp, ctl }) {
  const editing = ctl.editingId === exp.id
  const busy = ctl.busyId === exp.id

  return (
    <div className="psc__item">
      <div className="psc__item-title">{exp.title || 'Role'}</div>
      <div className="psc__item-sub">
        {exp.company || 'Company'}
        {(exp.start_year || exp.end_year) && ` · ${exp.start_year || ''}${exp.end_year ? ` — ${exp.end_year}` : ' — Present'}`}
      </div>
      <div className="evr__meta">
        <SourceBadges sources={exp.sources} />
        <ReviewBadge item={exp} />
      </div>

      {editing ? (
        <EditForm
          fields={EDIT_FIELDS}
          initial={{ role: exp.title, company: exp.company, stack: exp.skills_used, bullets: exp.bullets }}
          saving={busy}
          error={ctl.error}
          onSave={(fields) => ctl.run(exp.id, 'edit', fields)}
          onCancel={() => { ctl.setEditingId(null); ctl.setError('') }}
        />
      ) : (
        <>
          <div className="psc__pills">
            {(exp.skills_used || []).slice(0, 6).map((s) => <span key={s} className="psc__pill">{s}</span>)}
          </div>
          {exp.description && <p className="psc__item-desc" style={{ marginTop: 8 }}>{exp.description}</p>}
          <ReviewActions
            item={exp}
            busy={busy}
            onConfirm={() => ctl.run(exp.id, 'confirm')}
            onEdit={() => { ctl.setError(''); ctl.setEditingId(exp.id) }}
            onHide={() => ctl.run(exp.id, 'hide')}
            onRestore={() => ctl.run(exp.id, 'unhide')}
          />
        </>
      )}
    </div>
  )
}

function ExperiencesCard({ experiences = [], loading, onReview }) {
  const ctl = useReviewActions('experiences', onReview)
  const visible = experiences.filter((e) => !e.is_hidden)
  const hidden = experiences.filter((e) => e.is_hidden)

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
          </span>
          <h3 className="psc__title">Experiences</h3>
          {visible.length > 0 && <span className="psc__count">{visible.length}</span>}
        </div>
      </div>

      {ctl.error && ctl.editingId === null && <p className="psc__error">{ctl.error}</p>}

      {loading ? (
        <div className="psc__empty"><span className="psc__empty-text">Loading…</span></div>
      ) : visible.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No experiences yet — upload a resume or import LinkedIn to get started.</span>
        </div>
      ) : (
        visible.map((exp) => <ExperienceItem key={exp.id} exp={exp} ctl={ctl} />)
      )}

      <HiddenItems
        label="experience"
        items={hidden}
        nameOf={(e) => `${e.title} at ${e.company}`}
        busyId={ctl.busyId}
        onRestore={(e) => ctl.run(e.id, 'unhide')}
      />
    </Card>
  )
}

export default ExperiencesCard
