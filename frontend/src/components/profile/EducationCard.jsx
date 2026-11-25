import Card from '../common/Card'
import {
  EditForm, HiddenItems, ReviewActions, ReviewBadge, SourceBadges,
} from './evidence/ReviewControls'
import { useReviewActions } from './evidence/useReviewActions'
import './ProfileSectionCard.css'
import './evidence/EvidenceReview.css'

const EDIT_FIELDS = [
  { name: 'institution', label: 'Institution', kind: 'text' },
  { name: 'degree', label: 'Degree', kind: 'text' },
  { name: 'field_of_study', label: 'Field of study', kind: 'text' },
]

function EducationItem({ edu, ctl }) {
  const editing = ctl.editingId === edu.id
  const busy = ctl.busyId === edu.id

  return (
    <div className="psc__item">
      <div className="psc__item-title">{edu.institution || 'Institution'}</div>
      <div className="psc__item-sub">
        {[edu.degree, edu.field_of_study].filter(Boolean).join(' · ') || 'Degree'}
        {edu.graduation_year && <><br />{edu.graduation_year}</>}
      </div>
      <div className="evr__meta">
        <SourceBadges sources={edu.sources} />
        <ReviewBadge item={edu} />
      </div>

      {editing ? (
        <EditForm
          fields={EDIT_FIELDS}
          initial={edu}
          saving={busy}
          error={ctl.error}
          onSave={(fields) => ctl.run(edu.id, 'edit', fields)}
          onCancel={() => { ctl.setEditingId(null); ctl.setError('') }}
        />
      ) : (
        <ReviewActions
          item={edu}
          busy={busy}
          onConfirm={() => ctl.run(edu.id, 'confirm')}
          onEdit={() => { ctl.setError(''); ctl.setEditingId(edu.id) }}
          onHide={() => ctl.run(edu.id, 'hide')}
          onRestore={() => ctl.run(edu.id, 'unhide')}
        />
      )}
    </div>
  )
}

function EducationCard({ education = [], loading, onReview }) {
  const ctl = useReviewActions('education', onReview)
  const visible = education.filter((e) => !e.is_hidden)
  const hidden = education.filter((e) => e.is_hidden)

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 10l10-6 10 6-10 6z" />
              <path d="M6 12v6c0 1 2 3 6 3s6-2 6-3v-6" />
            </svg>
          </span>
          <h3 className="psc__title">Education</h3>
          {visible.length > 0 && <span className="psc__count">{visible.length}</span>}
        </div>
      </div>

      {ctl.error && ctl.editingId === null && <p className="psc__error">{ctl.error}</p>}

      {loading ? (
        <div className="psc__empty"><span className="psc__empty-text">Loading…</span></div>
      ) : visible.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No education records found — upload a resume or import LinkedIn.</span>
        </div>
      ) : (
        visible.map((edu) => <EducationItem key={edu.id} edu={edu} ctl={ctl} />)
      )}

      <HiddenItems
        label="education entry"
        items={hidden}
        nameOf={(e) => e.institution}
        busyId={ctl.busyId}
        onRestore={(e) => ctl.run(e.id, 'unhide')}
      />
    </Card>
  )
}

export default EducationCard
