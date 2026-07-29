import './ProjectCard.css'

const TIER_TONE = {
  'Flagship Project': 'flagship',
  'Career Project': 'career',
  'Learning Project': 'learning',
  'Prototype': 'prototype',
  'Archived': 'archived',
}

const LINK_STATUS_LABEL = {
  confirmed: null, // no badge needed — this is the healthy state
  broken_link: 'Link broken',
  suggested_match: 'Unconfirmed match',
  unmatched: null,
}

function formatUpdated(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return 'Updated Today'
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) return 'Updated Yesterday'
  return `Updated ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
}

function ProjectCard({ project, onOpen, curationAction, onExplain }) {
  const tone = TIER_TONE[project.tier] || 'career'
  const linkWarning = LINK_STATUS_LABEL[project.link_status]

  return (
    <article className="project-card">
      <div className="project-card__top">
        <div className="project-card__title-row">
          <h3 className="project-card__name">{project.name}</h3>
          <span className={`project-card__tier project-card__tier--${tone}`}>{project.tier}</span>
          <span className={`project-card__badge project-card__badge--${project.status}`}>
            {project.status === 'ongoing' ? 'Ongoing' : 'Completed'}
          </span>
          {linkWarning && <span className="project-card__link-warning">{linkWarning}</span>}
          {curationAction === 'hide_suggested' && (
            <span className="project-card__curation-warning">Consider hiding</span>
          )}
        </div>
      </div>

      <p className="project-card__tagline">{project.tagline}</p>
      {project.description && <p className="project-card__desc">{project.description}</p>}

      {project.engineering_tags?.length > 0 && (
        <div className="project-card__engineering">
          {project.engineering_tags.map((tag) => (
            <span key={tag} className="project-card__eng-pill">{tag}</span>
          ))}
        </div>
      )}

      {project.stack?.length > 0 && (
        <div className="project-card__stack">
          {project.stack.slice(0, 4).map((tech) => (
            <span key={tech} className="project-card__pill">{tech}</span>
          ))}
        </div>
      )}

      <div className="project-card__footer">
        <span className="project-card__updated">{formatUpdated(project.updated_at)}</span>
        <div className="project-card__footer-actions">
          {onExplain && (
            <button type="button" className="project-card__open" onClick={() => onExplain(project)}>
              Explain ✦
            </button>
          )}
          <button type="button" className="project-card__open" onClick={() => onOpen(project)}>
            Open ↗
          </button>
        </div>
      </div>
    </article>
  )
}

export default ProjectCard