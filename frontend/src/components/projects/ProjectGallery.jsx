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

function ProjectGallery({ projects, loading, leadProjectId, onOpenProject, onAddProject, onViewDetails }) {
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    if (filter === 'all') return projects
    if (filter === 'featured') return projects.filter((p) => p.is_featured)
    return projects.filter((p) => p.status === filter)
  }, [projects, filter])

  return (
    <div className="project-gallery">
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
        <div className="project-gallery__list">
          {filtered.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              isLead={project.id === leadProjectId}
              onOpen={onOpenProject}
              onViewDetails={onViewDetails}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export default ProjectGallery