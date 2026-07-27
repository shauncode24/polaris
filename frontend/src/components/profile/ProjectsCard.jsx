import Card from '../common/Card'
import './ProfileSectionCard.css'

function ProjectItem({ project, onDelete }) {
  const sources = project.sources || ['resume']
  const skills = project.skills_used || project.languages || []

  return (
    <div className="psc__item">
      <div className="psc__item-header">
        <div style={{ flex: 1 }}>
          <div className="psc__item-title">{project.name || 'Project'}</div>
          <div className="psc__pills" style={{ marginBottom: 8 }}>
            {sources.map((s) => (
              <span key={s} className="psc__pill">{s}</span>
            ))}
          </div>
          {project.description && (
            <div className="psc__item-desc">{project.description}</div>
          )}
          <div className="psc__pills">
            {skills.slice(0, 4).map((s) => (
              <span key={s} className="psc__pill">{s}</span>
            ))}
          </div>
        </div>
        <button
          type="button"
          className="psc__item-action-btn psc__item-action-btn--danger"
          onClick={() => onDelete(project.id)}
          aria-label="Delete project"
          style={{ alignSelf: 'flex-start', marginLeft: 8 }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
            <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
          </svg>
        </button>
      </div>
      <div className="psc__item-actions" style={{ marginTop: 10, justifyContent: 'flex-start' }}>
        <button type="button" className="psc__item-action-btn">Edit</button>
        <button type="button" className="psc__link-action" style={{ padding: 0, margin: 0, display: 'inline', fontSize: 13 }}>
          Explain for interview →
        </button>
      </div>
    </div>
  )
}

function ProjectsCard({ results, loading }) {
  const resumeProjects = results?.resume?.projects || []
  const githubRepos = (results?.github?.repositories || [])
    .sort((a, b) => (b.project_score?.overall || 0) - (a.project_score?.overall || 0))

  // Merge: prefer resume projects, supplement with top github repos
  const projects = resumeProjects.length > 0
    ? resumeProjects.map((p) => ({ ...p, sources: p.sources || ['resume'] }))
    : githubRepos.slice(0, 4).map((r) => ({
        id: r.name,
        name: r.name,
        description: r.description,
        languages: r.languages?.map((l) => l.language) || [],
        sources: ['github'],
      }))

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
          {projects.length > 0 && (
            <span className="psc__count">{projects.length}</span>
          )}
        </div>
        <button type="button" className="psc__add-btn">
          <span>+</span> Add project manually
        </button>
      </div>

      {loading ? (
        <div className="psc__empty">
          <span className="psc__empty-text">Loading…</span>
        </div>
      ) : projects.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No projects found — upload a resume or sync GitHub to populate.</span>
        </div>
      ) : (
        <div className="psc__project-grid">
          {projects.map((p, i) => (
            <ProjectItem key={p.id || i} project={p} onDelete={() => {}} />
          ))}
        </div>
      )}
    </Card>
  )
}

export default ProjectsCard
