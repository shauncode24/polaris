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

const STACK_OVERFLOW_LIMIT = 4
const CAPABILITY_LIMIT = 4

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

// Exactly one "health" badge — priority order matches how urgently a
// reader should act on it: unresolved risk > staleness > undersold >
// simply ready. Never stack more than one of these on a card.
function getHealthBadge(project) {
  if (project.claim_risk === 'high' || project.claim_risk === 'medium') {
    return { label: CLAIM_RISK_LABEL[project.claim_risk], tone: project.claim_risk }
  }
  if (project.abandonment_status) {
    return { label: ABANDONMENT_LABEL[project.abandonment_status], tone: project.abandonment_status }
  }
  if (project.claim_risk === 'undersold') {
    return { label: 'Undersold', tone: 'undersold' }
  }
  if (project.has_repo) {
    return { label: 'Interview Ready', tone: 'ready' }
  }
  return null
}

function ProjectCard({ project, isLead, onOpen, onViewDetails }) {
  const tone = TIER_TONE[project.tier] || 'career'
  const healthBadge = getHealthBadge(project)

  const stack = project.stack || []
  const visibleStack = stack.slice(0, STACK_OVERFLOW_LIMIT)
  const hiddenStackCount = stack.length - visibleStack.length

  const capabilities = project.engineering_tags || []
  const visibleCapabilities = capabilities.slice(0, CAPABILITY_LIMIT)

  return (
    <article
      className="project-row"
      onClick={() => onViewDetails?.(project)}
      role="button"
      tabIndex={0}
    >
      {/* Row 1 — identity: name, one-line description, tech stack */}
      <div className="project-row__identity">
        <div className="project-row__title-line">
          {project.is_featured && <span className="project-row__star" title="Featured">⭐</span>}
          <h3 className="project-row__name">{project.name}</h3>
          {isLead && <span className="project-row__lead-badge">Recommended lead</span>}
        </div>
        {project.tagline && <p className="project-row__tagline">{project.tagline}</p>}
        {stack.length > 0 && (
          <div className="project-row__stack">
            {visibleStack.map((tech) => (
              <span key={tech} className="project-row__pill">{tech}</span>
            ))}
            {hiddenStackCount > 0 && (
              <span className="project-row__pill project-row__pill--muted">+{hiddenStackCount} more</span>
            )}
          </div>
        )}
      </div>

      {/* Row 2 — capabilities (what engineering work actually happened) */}
      {visibleCapabilities.length > 0 && (
        <div className="project-row__capabilities">
          {visibleCapabilities.map((cap) => (
            <span key={cap} className="project-row__cap-pill">{cap}</span>
          ))}
        </div>
      )}

      {/* Row 3 — one badge per group: identity / health / metadata */}
      <div className="project-row__badges">
        <div className="project-row__badge-group">
          {project.rating != null && project.rating > 0 && <StarRating rating={project.rating} />}
          <span className={`project-row__tag project-row__tag--${tone}`}>{project.tier}</span>
          {healthBadge && (
            <span className={`project-row__tag project-row__tag--${healthBadge.tone}`}>{healthBadge.label}</span>
          )}
        </div>
        <div className="project-row__meta-group">
          <span className="project-row__meta">{formatUpdated(project.updated_at)}</span>
          {project.collaboration_mode && (
            <span className="project-row__meta project-row__meta--capitalize">{project.collaboration_mode}</span>
          )}
          {project.matched_repo_name && (
            <span className="project-row__meta project-row__meta--repo">
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
              {project.matched_repo_name}
            </span>
          )}
        </div>
      </div>

      {/* Row 4 — the only two actions a card ever needs */}
      <div className="project-row__actions">
        {project.has_repo && (
          <button
            type="button"
            className="project-row__action project-row__action--ghost"
            onClick={(e) => { e.stopPropagation(); onOpen(project) }}
          >
            GitHub ↗
          </button>
        )}
        <button
          type="button"
          className="project-row__action project-row__action--primary"
          onClick={(e) => { e.stopPropagation(); onViewDetails(project) }}
        >
          Open Details →
        </button>
      </div>
    </article>
  )
}

export default ProjectCard