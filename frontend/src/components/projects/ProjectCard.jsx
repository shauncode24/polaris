import StarRating from './StarRating'
import './ProjectCard.css'

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

function ProjectCard({ project, onOpen }) {
  return (
    <article className="project-card">
      <div className="project-card__top">
        <div className="project-card__title-row">
          <h3 className="project-card__name">{project.name}</h3>
          {project.is_featured && (
            <span className="project-card__badge project-card__badge--featured">Featured</span>
          )}
          <span className={`project-card__badge project-card__badge--${project.status}`}>
            {project.status === 'ongoing' ? 'Ongoing' : 'Completed'}
          </span>
        </div>
        <StarRating rating={project.rating} />
      </div>

      <p className="project-card__tagline">{project.tagline}</p>
      {project.description && <p className="project-card__desc">{project.description}</p>}

      {project.stack?.length > 0 && (
        <div className="project-card__stack">
          {project.stack.slice(0, 5).map((tech) => (
            <span key={tech} className="project-card__pill">{tech}</span>
          ))}
        </div>
      )}

      <div className="project-card__footer">
        <span className="project-card__updated">{formatUpdated(project.updated_at)}</span>
        <button type="button" className="project-card__open" onClick={() => onOpen(project)}>
          Open ↗
        </button>
      </div>
    </article>
  )
}

export default ProjectCard