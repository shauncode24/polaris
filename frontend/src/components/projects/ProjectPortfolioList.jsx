import { useMemo, useState } from 'react'
import ProjectRow from './ProjectRow'
import EmptyState from '../common/EmptyState'
import './ProjectPortfolioList.css'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'featured', label: 'Featured' },
  { key: 'ongoing', label: 'Ongoing' },
  { key: 'completed', label: 'Completed' },
]

// Replaces ProjectGallery.jsx. Same filter tabs, same EmptyState fallback —
// only the layout underneath changed, from a 2x2 card grid to a single
// bordered list of ProjectRow entries (doc: "SECTION 2 — ENGINEERING
// PORTFOLIO"). leadProjectId badges the top goal-aware-ranked project
// inline instead of a dedicated "Which project should lead?" panel.
function ProjectPortfolioList({
  projects,
  loading,
  leadProjectId,
  selectedProjectId,
  onSelect,
  onInterview,
  onAddProject,
}) {
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    if (filter === 'all') return projects
    if (filter === 'featured') return projects.filter((p) => p.is_featured)
    return projects.filter((p) => p.status === filter)
  }, [projects, filter])

  return (
    <section className="portfolio-list">
      <div className="portfolio-list__header">
        <div>
          <h2>Engineering portfolio</h2>
          <p className="portfolio-list__lead">
            What you built — and what each project proves about your engineering ability.
          </p>
        </div>
        <div className="portfolio-list__tabs" role="tablist">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              className={`portfolio-list__tab ${filter === f.key ? 'portfolio-list__tab--active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p className="portfolio-list__loading">Loading your projects…</p>
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
        <div className="portfolio-list__rows">
          {filtered.map((project) => (
            <ProjectRow
              key={project.id}
              project={project}
              isActive={project.id === selectedProjectId}
              isLeadProject={project.id === leadProjectId}
              onSelect={onSelect}
              onInterview={onInterview}
            />
          ))}
        </div>
      )}
    </section>
  )
}

export default ProjectPortfolioList