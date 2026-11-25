import { useState } from 'react'
import Card from '../common/Card'
import {
  EditForm, HiddenItems, ReviewActions, ReviewBadge, SourceBadges,
} from './evidence/ReviewControls'
import { useReviewActions } from './evidence/useReviewActions'
import './ProfileSectionCard.css'
import './evidence/EvidenceReview.css'

const EDIT_FIELDS = [
  { name: 'name', label: 'Name', kind: 'text' },
  { name: 'description', label: 'Description', kind: 'textarea' },
  { name: 'stack', label: 'Technologies (comma separated)', kind: 'comma' },
]

function ProjectItem({ project, ctl }) {
  const editing = ctl.editingId === project.id
  const busy = ctl.busyId === project.id

  return (
    <div className="psc__item">
      <div className="psc__item-title">{project.name || 'Project'}</div>
      <div className="evr__meta">
        <SourceBadges sources={project.sources} />
        <ReviewBadge item={project} />
        {project.repo && <span className="evr__repo">repo: {project.repo.name}</span>}
      </div>

      {editing ? (
        <EditForm
          fields={EDIT_FIELDS}
          initial={{ name: project.name, description: project.description, stack: project.skills_used }}
          saving={busy}
          error={ctl.error}
          onSave={(fields) => ctl.run(project.id, 'edit', fields)}
          onCancel={() => { ctl.setEditingId(null); ctl.setError('') }}
        />
      ) : (
        <>
          {project.description && <div className="psc__item-desc">{project.description}</div>}
          <div className="psc__pills">
            {(project.skills_used || []).slice(0, 6).map((s) => (
              <span key={s} className="psc__pill">{s}</span>
            ))}
          </div>
          <ReviewActions
            item={project}
            busy={busy}
            onConfirm={() => ctl.run(project.id, 'confirm')}
            onEdit={() => { ctl.setError(''); ctl.setEditingId(project.id) }}
            onHide={() => ctl.run(project.id, 'hide')}
            onRestore={() => ctl.run(project.id, 'unhide')}
          />
        </>
      )}
    </div>
  )
}

function PendingLinks({ links, busy, onLink, onDismiss }) {
  if (!links.length) return null
  return (
    <div className="evr__pending">
      <div className="evr__pending-title">Possible GitHub matches — are these the same project?</div>
      {links.map((l) => (
        <div key={l.project_id} className="evr__pending-row">
          <span><strong>{l.project_name}</strong> may be the repo <strong>{l.candidate_repo}</strong></span>
          <span className="evr__actions" style={{ marginTop: 0 }}>
            <button type="button" className="evr__btn evr__btn--primary" disabled={busy}
              onClick={() => onLink(l.project_id, l.candidate_repo)}>Link them</button>
            <button type="button" className="evr__btn" disabled={busy}
              onClick={() => onDismiss(l.project_id)}>Not the same</button>
          </span>
        </div>
      ))}
    </div>
  )
}

function ProjectsCard({ projects = [], pendingLinks = [], loading, onReview, onLink, onDismissLink }) {
  const ctl = useReviewActions('projects', onReview)
  const [linkBusy, setLinkBusy] = useState(false)

  // Linking or dismissing a suggested match changes the whole record, so the
  // page reloads it; a failure is shown the same way an edit failure is.
  async function withLinkBusy(action) {
    setLinkBusy(true)
    ctl.setError('')
    try {
      await action()
    } catch (err) {
      ctl.setError(err.message || 'That change could not be saved.')
    } finally {
      setLinkBusy(false)
    }
  }

  const visible = projects.filter((p) => !p.is_hidden)
  const hidden = projects.filter((p) => p.is_hidden)

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="5" cy="6" r="2" /><circle cx="19" cy="6" r="2" /><circle cx="12" cy="18" r="2" />
              <path d="M7 6h10" /><path d="M6.5 7.7L11 16.3" /><path d="M17.5 7.7L13 16.3" />
            </svg>
          </span>
          <h3 className="psc__title">Projects</h3>
          {visible.length > 0 && <span className="psc__count">{visible.length}</span>}
        </div>
      </div>

      <PendingLinks
        links={pendingLinks}
        busy={linkBusy}
        onLink={(id, repo) => withLinkBusy(() => onLink(id, repo))}
        onDismiss={(id) => withLinkBusy(() => onDismissLink(id))}
      />

      {ctl.error && ctl.editingId === null && <p className="psc__error">{ctl.error}</p>}

      {loading ? (
        <div className="psc__empty"><span className="psc__empty-text">Loading…</span></div>
      ) : visible.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No projects yet — upload a resume or sync GitHub to populate.</span>
        </div>
      ) : (
        <div className="psc__project-grid">
          {visible.map((p) => <ProjectItem key={p.id} project={p} ctl={ctl} />)}
        </div>
      )}

      <HiddenItems
        label="project"
        items={hidden}
        nameOf={(p) => p.name}
        busyId={ctl.busyId}
        onRestore={(p) => ctl.run(p.id, 'unhide')}
      />
    </Card>
  )
}

export default ProjectsCard
