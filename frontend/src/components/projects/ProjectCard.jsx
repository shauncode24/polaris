import StarRating from './StarRating'
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
  if (date.toDateString() === today.toDateString()) return 'Updated today'
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) return 'Updated yesterday'
  return `Updated ${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
}

function ProjectCard({ project, isLead, onOpen, onViewDetails }) {
  const tone = TIER_TONE[project.tier] || 'career'

  return (
    <article
      className="project-row"
      onClick={() => onViewDetails?.(project)}
      role="button"
      tabIndex={0}
    >
      <div className="project-row__left">
        <div className="project-row__title-line">
          <h3 className="project-row__name">{project.name}</h3>
          {project.is_featured && <span className="project-row__star" title="Featured">✨</span>}
          {isLead && <span className="project-row__lead-badge">Recommended lead</span>}
        </div>
        <p className="project-row__tagline">{project.tagline}</p>
        {project.stack?.length > 0 && (
          <div className="project-row__stack">
            {project.stack.slice(0, 5).map((tech) => (
              <span key={tech} className="project-row__pill">{tech}</span>
            ))}
          </div>
        )}
        {project.description && <p className="project-row__desc">{project.description}</p>}
      </div>

      <div className="project-row__center">
        <span className={`project-row__tier project-row__tier--${tone}`}>{project.tier}</span>
        {project.rating != null && project.rating > 0 && <StarRating rating={project.rating} />}
        {project.engineering_tags?.length > 0 && (
          <div className="project-row__caps">
            {project.engineering_tags.slice(0, 3).map((tag) => (
              <span key={tag} className="project-row__cap-pill">{tag}</span>
            ))}
          </div>
        )}
        {(project.claim_risk || project.abandonment_status) && (
          <div className="project-row__flags">
            {project.claim_risk && (
              <span className={`project-row__flag project-row__flag--${project.claim_risk}`}>
                {CLAIM_RISK_LABEL[project.claim_risk] || project.claim_risk}
              </span>
            )}
            {project.abandonment_status && (
              <span className={`project-row__flag project-row__flag--${project.abandonment_status}`}>
                {ABANDONMENT_LABEL[project.abandonment_status] || project.abandonment_status}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="project-row__right">
        <span className={`project-row__status project-row__status--${project.status}`}>
          {project.status === 'ongoing' ? 'Ongoing' : project.status === 'unknown' ? 'Unknown' : 'Completed'}
        </span>
        <span className="project-row__updated">{formatUpdated(project.updated_at)}</span>
        {project.collaboration_mode && (
          <span className="project-row__collab">{project.collaboration_mode}</span>
        )}
        {project.matched_repo_name && (
          <span className="project-row__repo">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
            {project.matched_repo_name}
          </span>
        )}
        <button
          type="button"
          className="project-row__open"
          onClick={(e) => { e.stopPropagation(); onOpen(project) }}
        >
          Open ↗
        </button>
      </div>
    </article>
  )
}

export default ProjectCard