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
          {project.rating != null && project.rating > 0 && (
            <StarRating rating={project.rating} />
          )}
          {project.is_featured && (
            <span className="project-card__badge project-card__badge--featured">✨ Featured</span>
          )}
          <span className={`project-card__tier project-card__tier--${tone}`}>{project.tier}</span>
          <span className={`project-card__badge project-card__badge--${project.status}`}>
            {project.status === 'ongoing' ? 'Ongoing' : project.status === 'unknown' ? 'Unknown' : 'Completed'}
          </span>
        </div>
      </div>

      {project.matched_repo_name && (
        <div className="project-card__github-meta">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
          <span className="project-card__repo-name">{project.matched_repo_name}</span>
          {project.collaboration_mode && (
            <span className="project-card__github-signal">{project.collaboration_mode}</span>
          )}
          {project.commit_hygiene_score != null && (
            <span className="project-card__github-signal">Hygiene: {project.commit_hygiene_score}</span>
          )}
        </div>
      )}

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