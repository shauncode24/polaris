import { useMemo, useState } from 'react'
import ProjectCard from './ProjectCard'
import EmptyState from '../common/EmptyState'
import './ProjectGallery.css'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'featured', label: 'Featured' },
  { key: 'ongoing', label: 'Ongoing' },
  { key: 'completed', label: 'Completed' },
]

function ProjectGallery({ projects, loading, onOpenProject, onAddProject, curationByProjectId, onExplainProject }) {
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    if (filter === 'all') return projects
    if (filter === 'featured') return projects.filter((p) => p.is_featured)
    return projects.filter((p) => p.status === filter)
  }, [projects, filter])

  return (
    <section className="project-gallery">
      <div className="project-gallery__header">
        <div>
          <h2>Project gallery</h2>
          <p className="project-gallery__lead">Large, evidence-rich work — not a passive card list.</p>
        </div>
        <div className="project-gallery__tabs" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              className={`project-gallery__tab ${filter === f.key ? 'project-gallery__tab--active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="project-gallery__loading">Loading your projects…</p>
      ) : filtered.length === 0 ? (
        <EmptyState
          message={
            projects.length === 0
              ? 'No projects yet — upload a resume or sync GitHub to populate this page.'
              : 'No projects match this filter.'
          }
          ctaLabel={projects.length === 0 ? 'Add a project' : undefined}
          onCta={projects.length === 0 ? onAddProject : undefined}
        />
      ) : (
        <div className="project-gallery__grid">
          {filtered.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onOpen={onOpenProject}
              curationAction={curationByProjectId?.[project.id]}
              onExplain={onExplainProject}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default ProjectGallery