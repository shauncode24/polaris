// frontend/src/components/job-intelligence/JobIntelligenceResults.jsx
import { useState } from 'react'
import CompanyIntelligenceCard from './CompanyIntelligenceCard'
import './JobIntelligenceResults.css'

const SENIORITY_LABELS = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid-level',
  senior: 'Senior',
  staff: 'Staff / Principal',
  unspecified: 'Not specified',
}

function seniorityBadgeClass(level) {
  if (level === 'senior' || level === 'staff') return 'ji-seniority-badge--senior'
  if (level === 'mid') return 'ji-seniority-badge--mid'
  if (level === 'junior' || level === 'intern') return 'ji-seniority-badge--junior'
  return 'ji-seniority-badge--neutral'
}

function qualityBadgeClass(label) {
  if (label === 'High') return 'ji-quality-badge--high'
  if (label === 'Medium') return 'ji-quality-badge--medium'
  return 'ji-quality-badge--low'
}

function EnrichedSkillGroup({ title, skills, dotClass }) {
  if (!skills || skills.length === 0) return null
  return (
    <div className="ji-skill-group">
      <h4><span className={`ji-skill-dot ${dotClass}`} /> {title} <span className="ji-skill-count">{skills.length}</span></h4>
      <div className="ji-skill-chips">
        {skills.map((s) => (
          <span key={s.canonical} className="ji-skill-chip">
            {s.canonical.replace(/_/g, ' ')}
            <span className="ji-skill-chip__category">{s.category}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function JobIntelligenceResults({ data }) {
  const [showRaw, setShowRaw] = useState(false)
  const job = data.job_intelligence
  const company = data.company_intelligence

  const seniority = job.seniority_signal || {}
  const quality = job.extraction_quality || {}

  return (
    <div className="ji-results">
      {/* Header */}
      <div className="ji-results__card ji-results__header">
        <div className="ji-results__header-main">
          <h1>{job.role || 'Untitled role'}</h1>
          {job.company && <p className="ji-results__company">{job.company}</p>}
        </div>
        <div className="ji-results__header-badges">
          <span className={`ji-seniority-badge ${seniorityBadgeClass(seniority.level)}`}>
            {SENIORITY_LABELS[seniority.level] || 'Not specified'}
          </span>
          <span className={`ji-quality-badge ${qualityBadgeClass(quality.label)}`}>
            {quality.label || 'Low'} confidence extraction
          </span>
        </div>
      </div>

      {/* Seniority evidence */}
      {seniority.evidence?.length > 0 && (
        <div className="ji-results__card">
          <h2>Seniority signal</h2>
          <p className="ji-results__card-lead">{seniority.confidence} confidence — based on:</p>
          <ul className="ji-results__evidence-list">
            {seniority.evidence.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}

      {/* Extraction quality reasons */}
      {quality.reasons?.length > 0 && (
        <div className="ji-results__card">
          <h2>Extraction confidence</h2>
          <ul className="ji-results__evidence-list">
            {quality.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* Required / implicit / nice-to-have skills */}
      <div className="ji-results__card">
        <h2>What this role requires</h2>
        <div className="ji-skill-groups">
          <EnrichedSkillGroup title="Required" skills={job.enriched_required_skills} dotClass="ji-skill-dot--required" />
          <EnrichedSkillGroup title="Implicit" skills={job.enriched_implicit_skills} dotClass="ji-skill-dot--implicit" />
          <EnrichedSkillGroup title="Nice to have" skills={job.enriched_nice_to_have} dotClass="ji-skill-dot--nice" />
        </div>
      </div>

      {/* Architecture topics */}
      {job.architecture_topics?.length > 0 && (
        <div className="ji-results__card">
          <h2>Architecture & system-design topics</h2>
          <div className="ji-tag-list">
            {job.architecture_topics.map((t) => <span key={t} className="ji-tag">{t}</span>)}
          </div>
        </div>
      )}

      {/* Resume keywords */}
      {job.resume_keywords?.length > 0 && (
        <div className="ji-results__card">
          <h2>Resume keywords</h2>
          <p className="ji-results__card-lead">Literal terms worth surfacing on a resume for this role</p>
          <div className="ji-tag-list">
            {job.resume_keywords.map((k) => <span key={k} className="ji-tag ji-tag--muted">{k}</span>)}
          </div>
        </div>
      )}

      {/* Interview focus areas */}
      {job.interview_focus_areas?.length > 0 && (
        <div className="ji-results__card">
          <h2>Interview focus areas</h2>
          <p className="ji-results__card-lead">What this role's interview loop would plausibly probe — same for every candidate targeting it</p>
          <div className="ji-tag-list">
            {job.interview_focus_areas.map((a) => <span key={a} className="ji-tag">{a}</span>)}
          </div>
        </div>
      )}

      {/* Company Intelligence — own card, own component */}
      <CompanyIntelligenceCard company={company} />

      {/* Raw JSON */}
      <div className="ji-results__card">
        <button type="button" className="ji-results__raw-toggle" onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide raw JSON response' : 'Show raw JSON response'}
        </button>
        {showRaw && <pre className="ji-results__raw-json">{JSON.stringify(data, null, 2)}</pre>}
      </div>
    </div>
  )
}

export default JobIntelligenceResults