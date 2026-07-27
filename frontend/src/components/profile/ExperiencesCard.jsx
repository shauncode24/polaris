import { useState } from 'react'
import Card from '../common/Card'
import { IconTrash } from '../icons/OnboardingIcons'
import { IconWorkflow } from '../icons/Icons'
import './ProfileSectionCard.css'

function ExperienceItem({ exp, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const skills = exp.skills_used || []
  const sources = exp.sources || ['resume']

  return (
    <div className="psc__item">
      <div className="psc__item-header">
        <div>
          <div className="psc__item-title">{exp.title || 'Role'}</div>
          <div className="psc__item-sub">
            {exp.company || 'Company'}
            {(exp.start_year || exp.end_year) && ` · ${exp.start_year || ''}${exp.end_year ? ` — ${exp.end_year}` : ' — Present'}`}
          </div>
          <div className="psc__pills">
            {skills.slice(0, 4).map((s) => (
              <span key={s} className="psc__pill">{s}</span>
            ))}
            {sources.map((s) => (
              <span key={s} className="psc__pill">{s}</span>
            ))}
          </div>
        </div>
        <div className="psc__item-actions">
          <button type="button" className="psc__item-action-btn">Edit</button>
          <button
            type="button"
            className="psc__item-action-btn psc__item-action-btn--danger"
            onClick={() => onDelete(exp.id)}
            aria-label="Delete experience"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
              <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
            </svg>
          </button>
        </div>
      </div>

      <button
        type="button"
        className="psc__expand-btn"
        onClick={() => setExpanded((v) => !v)}
      >
        View evidence {expanded ? '▲' : '▾'}
      </button>

      {expanded && exp.description && (
        <p className="psc__item-desc" style={{ marginTop: 8 }}>{exp.description}</p>
      )}
    </div>
  )
}

function ExperiencesCard({ results, loading }) {
  const experiences = results?.resume?.experiences || []

  function handleDelete(id) {
    // Local only for now – no backend DELETE endpoint wired
  }

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
            </svg>
          </span>
          <h3 className="psc__title">Experiences</h3>
          {experiences.length > 0 && (
            <span className="psc__count">{experiences.length}</span>
          )}
        </div>
        <button type="button" className="psc__add-btn">
          <span>+</span> Add experience manually
        </button>
      </div>

      {loading ? (
        <div className="psc__empty">
          <span className="psc__empty-text">Loading…</span>
        </div>
      ) : experiences.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No experiences yet — upload a resume to get started.</span>
        </div>
      ) : (
        experiences.map((exp, i) => (
          <ExperienceItem
            key={exp.id || i}
            exp={exp}
            onDelete={handleDelete}
          />
        ))
      )}
    </Card>
  )
}

export default ExperiencesCard
