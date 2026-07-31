import './ProjectCard.css'

const TIER_TONE = {
  'Flagship Project': 'flagship',
  'Career Project': 'career',
  'Learning Project': 'learning',
  'Prototype': 'prototype',
  'Archived': 'archived',
}

const CLAIM_RISK_LABEL = { high: 'Unsupported claims', medium: 'Claim mismatch', undersold: 'Undersold' }
const ABANDONMENT_LABEL = { resume_it: 'Resume this', retire_it: 'Consider retiring' }

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

function ProjectCard({ project, onOpen, onViewDetails }) {
  const tone = TIER_TONE[project.tier] || 'career'

  return (
    <article className="project-card" onClick={() => onViewDetails?.(project)} role="button" tabIndex={0}>
      <div className="project-card__top">
        <div className="project-card__title-row">
          <h3 className="project-card__name">{project.name}</h3>
          <span className={`project-card__tier project-card__tier--${tone}`}>{project.tier}</span>
          <span className={`project-card__badge project-card__badge--${project.status}`}>
            {project.status === 'ongoing' ? 'Ongoing' : 'Completed'}
          </span>
        </div>
      </div>

      {(project.claim_risk || project.abandonment_status) && (
        <div className="project-card__flags">
          {project.claim_risk && (
            <span className={`project-card__flag project-card__flag--${project.claim_risk}`}>
              {CLAIM_RISK_LABEL[project.claim_risk] || project.claim_risk}
            </span>
          )}
          {project.abandonment_status && (
            <span className={`project-card__flag project-card__flag--${project.abandonment_status}`}>
              {ABANDONMENT_LABEL[project.abandonment_status] || project.abandonment_status}
            </span>
          )}
        </div>
      )}

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
        <button
          type="button"
          className="project-card__open"
          onClick={(e) => {
            e.stopPropagation()
            onOpen(project)
          }}
        >
          Open ↗
        </button>
      </div>
    </article>
  )
}

export default ProjectCard