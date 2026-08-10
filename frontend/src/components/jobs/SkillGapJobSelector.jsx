import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import './SkillGapJobSelector.css'

const SENIORITY_LABELS = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid-level',
  senior: 'Senior',
  staff: 'Staff+',
  unspecified: null,
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function SkillGapJobSelector({ jobs, selectedId, onSelect, loading }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  if (loading) {
    return <div className="sgsel sgsel--loading">Loading your parsed roles…</div>
  }

  if (!jobs || jobs.length === 0) {
    return (
      <div className="sgsel sgsel--empty">
        <div className="sgsel__empty-text">
          <strong>No parsed job descriptions yet.</strong>
          <p>Analyze a role in Job Intelligence first — Skill Gap compares your profile against roles that are already parsed.</p>
        </div>
        <Link to="/job-intelligence" className="sgsel__cta">Go to Job Intelligence →</Link>
      </div>
    )
  }

  const selected = jobs.find((j) => j.id === selectedId)

  return (
    <div className="sgsel" ref={rootRef}>
      <span className="sgsel__label">Compare your profile against a job</span>

      <button type="button" className="sgsel__trigger" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {selected ? (
          <span className="sgsel__trigger-text">
            <strong>{selected.role || 'Untitled role'}</strong>
            {selected.company && <span className="sgsel__trigger-company"> at {selected.company}</span>}
          </span>
        ) : (
          <span className="sgsel__trigger-placeholder">Select a parsed role…</span>
        )}
        <span className={`sgsel__chevron ${open ? 'sgsel__chevron--open' : ''}`}>▾</span>
      </button>

      {open && (
        <div className="sgsel__panel">
          {jobs.map((j) => (
            <button
              key={j.id}
              type="button"
              className={`sgsel__option ${j.id === selectedId ? 'sgsel__option--active' : ''}`}
              onClick={() => { onSelect(j.id); setOpen(false) }}
            >
              <div className="sgsel__option-main">
                <span className="sgsel__option-role">{j.role || 'Untitled role'}</span>
                <span className="sgsel__option-company">{j.company || '—'}</span>
              </div>
              <div className="sgsel__option-meta">
                {SENIORITY_LABELS[j.seniority_level] && (
                  <span className="sgsel__pill">{SENIORITY_LABELS[j.seniority_level]}</span>
                )}
                <span className="sgsel__option-date">{formatDate(j.created_at)}</span>
              </div>
            </button>
          ))}
          <Link to="/job-intelligence" className="sgsel__panel-cta" onClick={() => setOpen(false)}>
            + Analyze a new role
          </Link>
        </div>
      )}
    </div>
  )
}

export default SkillGapJobSelector