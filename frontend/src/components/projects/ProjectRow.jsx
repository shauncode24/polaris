import StarRating from './StarRating'
import './ProjectRow.css'

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
  if (date.toDateString() === today.toDateString()) return 'Today'
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// One project = one horizontal row. Left: identity + stack + description.
// Center: capabilities + status flags. Right: recency + collaboration mode
// + primary actions. Replaces ProjectCard's 2x2 grid tile — same data
// shape, no card chrome, consistent row height regardless of description
// length (description is single-line clamped here, not 3-line).
function ProjectRow({ project, isActive, isLeadProject, onSelect, onInterview }) {
  const tone = TIER_TONE[project.tier] || 'career'

  return (
    <div
      className={`project-row ${isActive ? 'project-row--active' : ''}`}
      onClick={() => onSelect?.(project)}
      role="button"
      tabIndex={0}
    >
      <div className="project-row__main">
        <div className="project-row__title-line">
          {project.is_featured && <span className="project-row__star" title="Featured">⭐</span>}
          <span className="project-row__name">{project.name}</span>
          <span className={`project-row__tier project-row__tier--${tone}`}>{project.tier}</span>
          {project.rating != null && project.rating > 0 && <StarRating rating={project.rating} size={11} />}
          {isLeadProject && <span className="project-row__lead">Recommended lead</span>}
        </div>
        {project.stack?.length > 0 && (
          <div className="project-row__stack">
            {project.stack.slice(0, 4).map((tech) => (
              <span key={tech} className="project-row__stack-item">{tech}</span>
            ))}
          </div>
        )}
        {project.description && <p className="project-row__desc">{project.description}</p>}
      </div>

      <div className="project-row__center">
        {project.engineering_tags?.length > 0 && (
          <div className="project-row__tags">
            {project.engineering_tags.slice(0, 3).map((tag) => (
              <span key={tag} className="project-row__tag">{tag}</span>
            ))}
          </div>
        )}
        <div className="project-row__flags">
          <span className={`project-row__status project-row__status--${project.status}`}>
            {project.status === 'ongoing' ? 'Ongoing' : project.status === 'unknown' ? 'Unknown' : 'Completed'}
          </span>
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
      </div>

      <div className="project-row__side">
        <span className="project-row__updated">Updated {formatUpdated(project.updated_at)}</span>
        {project.matched_repo_name && (
          <span className="project-row__collab">{project.collaboration_mode || 'Solo'}</span>
        )}
        <div className="project-row__actions" onClick={(e) => e.stopPropagation()}>
          <button type="button" className="project-row__action" onClick={() => onSelect?.(project)}>Open</button>
          <button type="button" className="project-row__action" onClick={() => onInterview?.(project)}>Interview</button>
        </div>
      </div>
    </div>
  )
}

export default ProjectRow