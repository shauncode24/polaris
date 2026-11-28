// frontend/src/components/job-intelligence/JobLibrary.jsx
import { useState } from 'react'
import './JobLibrary.css'

const MAX_COMPARED = 4

const SENIORITY_LABELS = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid',
  senior: 'Senior',
  staff: 'Staff+',
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function jobName(job) {
  return `${job.role || 'Untitled role'}${job.company ? ` at ${job.company}` : ''}`
}

function JobLibrary({ items, loading, busy, onOpen, onSetPrimary, onDelete, onCompare }) {
  const [checked, setChecked] = useState([])
  // Ignore ticks left over from jobs that have since been deleted.
  const selected = checked.filter((id) => items.some((job) => job.id === id))

  function toggle(id) {
    setChecked(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  function confirmDelete(job) {
    const message =
      `Delete "${jobName(job)}"? Its match results and tailored resumes are removed. ` +
      'Goals that targeted it are kept, without the link.'
    if (window.confirm(message)) onDelete(job.id)
  }

  return (
    <section className="job-library">
      <div className="job-library__header">
        <div>
          <h3>Your jobs</h3>
          <p>The primary target is what the career planner and interview practice work toward.</p>
        </div>
        <button
          type="button"
          className="job-library__compare"
          disabled={busy || selected.length < 2 || selected.length > MAX_COMPARED}
          onClick={() => onCompare(selected)}
        >
          Compare{selected.length ? ` (${selected.length})` : ''}
        </button>
      </div>

      {loading ? (
        <p className="job-library__empty">Loading your jobs…</p>
      ) : items.length === 0 ? (
        <p className="job-library__empty">No jobs saved yet. Add a job description to get started.</p>
      ) : (
        <>
          <p className="job-library__hint">Tick two to {MAX_COMPARED} jobs to compare them.</p>
          <ul className="job-library__list">
            {items.map((job) => (
              <li key={job.id} className={`job-library__item ${job.is_primary ? 'job-library__item--primary' : ''}`}>
                <input
                  type="checkbox"
                  aria-label={`Compare ${jobName(job)}`}
                  checked={selected.includes(job.id)}
                  disabled={!selected.includes(job.id) && selected.length >= MAX_COMPARED}
                  onChange={() => toggle(job.id)}
                />
                <button type="button" className="job-library__open" onClick={() => onOpen(job.id)}>
                  <span className="job-library__role">{job.role || 'Untitled role'}</span>
                  <span className="job-library__meta">
                    {[job.company, SENIORITY_LABELS[job.seniority_level], formatDate(job.created_at)]
                      .filter(Boolean)
                      .join(' · ')}
                  </span>
                </button>
                <div className="job-library__actions">
                  <button
                    type="button"
                    className={`job-library__primary ${job.is_primary ? 'job-library__primary--on' : ''}`}
                    aria-pressed={job.is_primary}
                    disabled={busy}
                    onClick={() => onSetPrimary(job.id, !job.is_primary)}
                  >
                    {job.is_primary ? '★ Primary target' : 'Set as primary'}
                  </button>
                  <button
                    type="button"
                    className="job-library__delete"
                    disabled={busy}
                    onClick={() => confirmDelete(job)}
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}

export default JobLibrary
