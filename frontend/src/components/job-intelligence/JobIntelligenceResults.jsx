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

const PROFICIENCY_LABELS = {
  good_knowledge: 'Good knowledge',
  hands_on: 'Hands-on',
  exposure: 'Exposure',
  familiarity: 'Familiarity',
  not_specified: '',
}

const EXPERIENCE_TYPE_LABELS = {
  internship_or_project: 'Internships / projects accepted',
  professional: 'Professional experience required',
  not_specified: '',
}

// Lightweight client-side bucketing for "Interview preparation signals" so
// it reads as an interpretation rather than a re-listing of requirements
// (spec §21). Backend gives us a flat inferred[] list with no category
// per-item, so this is a heuristic grouping only — nothing authoritative
// is derived here, it's purely a presentation aid.
const FOUNDATION_KEYWORDS = ['git', 'sdlc', 'database', 'data structure', 'algorithm', 'dsa', 'testing', 'debug', 'query', 'version control']
const DESIGN_KEYWORDS = ['design pattern', 'scalab', 'performance', 'architecture', 'system design', 'modular', 'trade-off', 'leadership', 'non-functional', 'reliab']

function bucketInterviewFocus(items) {
  const foundations = []
  const design = []
  const stack = []
  for (const item of items) {
    const lowered = item.toLowerCase()
    if (FOUNDATION_KEYWORDS.some((k) => lowered.includes(k))) foundations.push(item)
    else if (DESIGN_KEYWORDS.some((k) => lowered.includes(k))) design.push(item)
    else stack.push(item)
  }
  return { foundations, design, stack }
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

const NAV_SECTIONS = [
  { id: 'ji-sec-overview', label: 'Overview' },
  { id: 'ji-sec-requirements', label: 'Requirements' },
  { id: 'ji-sec-qualifications', label: 'Qualifications' },
  { id: 'ji-sec-architecture', label: 'Architecture' },
  { id: 'ji-sec-company', label: 'Company' },
  { id: 'ji-sec-resume', label: 'Resume' },
  { id: 'ji-sec-interview', label: 'Interview' },
]

function SectionNav() {
  function scrollTo(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  return (
    <nav className="ji-section-nav" aria-label="Jump to section">
      {NAV_SECTIONS.map((s) => (
        <button key={s.id} type="button" className="ji-section-nav__link" onClick={() => scrollTo(s.id)}>
          {s.label}
        </button>
      ))}
    </nav>
  )
}

function GlanceRow({ label, value }) {
  if (!value) return null
  return (
    <div className="ji-glance__row">
      <span className="ji-glance__label">{label}</span>
      <span className="ji-glance__value">{value}</span>
    </div>
  )
}

function SkillChip({ skill }) {
  const proficiencyLabel = PROFICIENCY_LABELS[skill.proficiency_signal]
  const isInferred = skill.requirement_type === 'implicit'
  return (
    <div className="ji-skill-chip" title={skill.evidence || undefined}>
      <span className="ji-skill-chip__name">{skill.canonical.replace(/_/g, ' ')}</span>
      <span className="ji-skill-chip__meta">
        {proficiencyLabel && <>{proficiencyLabel} · </>}
        {skill.category}
        {isInferred && (
          <span className={`ji-skill-chip__inferred ji-skill-chip__inferred--${skill.confidence}`}>
            {' '}· inferred
          </span>
        )}
      </span>
    </div>
  )
}

function SkillGroup({ title, tone, skills }) {
  if (!skills || skills.length === 0) return null
  return (
    <div className={`ji-skillgroup ji-skillgroup--${tone}`}>
      <h4 className="ji-skillgroup__title">
        {title} <span className="ji-skill-count">{skills.length}</span>
      </h4>
      <div className="ji-skill-chips">
        {skills.map((s) => <SkillChip key={s.canonical} skill={s} />)}
      </div>
    </div>
  )
}

function JobIntelligenceResults({ data }) {
  const [showRaw, setShowRaw] = useState(false)
  const [resumeOpen, setResumeOpen] = useState(false)
  const job = data.job_intelligence
  const company = data.company_intelligence

  const seniority = job.seniority_signal || {}
  const quality = job.extraction_quality || {}
  const identity = job.role_identity || {}
  const qualifications = job.qualification_requirements || {}
  const interviewFocus = job.interview_focus || {}
  const experience = qualifications.experience || null
  const keywordTiers = job.resume_keyword_tiers || {}
  const resumeRelevantKeywords =
    keywordTiers.resume_relevant?.length > 0 ? keywordTiers.resume_relevant : job.resume_keywords || []

  const hasQualifications =
    qualifications.education?.length > 0 || qualifications.eligibility?.length > 0 || !!experience

  const secondaryLine = [identity.location, identity.function, identity.designation].filter(Boolean).join(' · ')

  const { foundations, design, stack } = bucketInterviewFocus(interviewFocus.inferred || [])

  return (
    <div className="ji-results">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div id="ji-sec-overview" className="ji-header">
        <div className="ji-header__main">
          <h1>{job.role || 'Untitled role'}</h1>
          {job.company && <p className="ji-header__company">{job.company}</p>}
          {secondaryLine && <p className="ji-header__secondary">{secondaryLine}</p>}
        </div>
        <div className="ji-header__badges">
          <span
            className={`ji-seniority-badge ${seniorityBadgeClass(seniority.level)}`}
            title={seniority.evidence?.length ? seniority.evidence.join(' • ') : 'Inferred from the role title/designation.'}
          >
            {SENIORITY_LABELS[seniority.level] || 'Not specified'}
          </span>
          <span
            className={`ji-quality-badge ${qualityBadgeClass(quality.label)}`}
            title={quality.reasons?.length ? quality.reasons.join(' • ') : 'Based on completeness of information extracted from the source JD.'}
          >
            {quality.label || 'Low'}-confidence extraction
          </span>
        </div>
      </div>

      <SectionNav />

      {/* ── Job at a glance ────────────────────────────────────── */}
      <div className="ji-glance">
        <GlanceRow label="Role" value={job.role} />
        <GlanceRow label="Location" value={identity.location} />
        <GlanceRow label="Function" value={identity.function} />
        <GlanceRow label="Department" value={identity.department} />
        <GlanceRow label="Designation" value={identity.designation} />
        <GlanceRow label="Grade" value={identity.grade} />
        <GlanceRow label="Reports to" value={identity.reports_to} />
        <GlanceRow label="Employment type" value={identity.employment_type} />
      </div>
      {identity.designation && identity.grade && (
        <p className="ji-note">
          Designation and grade are shown separately from seniority — a "{identity.grade}" grade doesn't
          necessarily mean a senior engineering level.
        </p>
      )}

      {/* ── Role purpose ───────────────────────────────────────── */}
      {job.job_purpose && (
        <div className="ji-block">
          <h3 className="ji-block__title">Role purpose</h3>
          <p className="ji-block__text">{job.job_purpose}</p>
        </div>
      )}

      {/* ── Responsibilities ───────────────────────────────────── */}
      {job.responsibilities?.length > 0 && (
        <div className="ji-block">
          <h3 className="ji-block__title">What you'll do</h3>
          <ol className="ji-numbered-list">
            {job.responsibilities.map((r, i) => (
              <li key={i}><span className="ji-numbered-list__index">{String(i + 1).padStart(2, '0')}</span>{r}</li>
            ))}
          </ol>
        </div>
      )}

      {/* ── Requirements (centerpiece) ─────────────────────────── */}
      <div id="ji-sec-requirements" className="ji-card ji-card--primary">
        <h2>What this role requires</h2>
        <p className="ji-card__lead">
          Includes named technologies as well as explicitly stated processes and practices — not just product names.
        </p>
        <SkillGroup title="Required" tone="required" skills={job.enriched_required_skills} />
        <SkillGroup title="Implicit" tone="implicit" skills={job.enriched_implicit_skills} />
        <SkillGroup title="Nice to have" tone="nice" skills={job.enriched_nice_to_have} />
      </div>

      {/* ── Qualifications ─────────────────────────────────────── */}
      {hasQualifications && (
        <div id="ji-sec-qualifications" className="ji-card">
          <h2>Qualifications & eligibility</h2>

          {qualifications.education?.length > 0 && (
            <div className="ji-results__row">
              <h4>Education</h4>
              <div className="ji-tag-list">
                {qualifications.education.map((e, i) => <span key={i} className="ji-tag">{e}</span>)}
              </div>
            </div>
          )}

          {qualifications.eligibility?.length > 0 && (
            <div className="ji-results__row">
              <h4>Eligibility</h4>
              <div className="ji-tag-list">
                {qualifications.eligibility.map((e, i) => (
                  <span key={i} className="ji-tag">{e.requirement}{e.detail ? ` — ${e.detail}` : ''}</span>
                ))}
              </div>
            </div>
          )}

          {experience && (
            <div className="ji-results__row">
              <h4>Experience</h4>
              <div className="ji-experience">
                {PROFICIENCY_LABELS[experience.proficiency_signal] && (
                  <span className="ji-experience__primary">{PROFICIENCY_LABELS[experience.proficiency_signal]}</span>
                )}
                {experience.domain && (
                  <span className="ji-experience__domain">{experience.domain.replace(/_/g, ' ')}</span>
                )}
                {EXPERIENCE_TYPE_LABELS[experience.experience_type] && (
                  <p className="ji-experience__type">{EXPERIENCE_TYPE_LABELS[experience.experience_type]}</p>
                )}
                {experience.minimum_years != null && (
                  <p className="ji-experience__type">{experience.minimum_years}+ years stated</p>
                )}
                {experience.raw && (
                  <details className="ji-details">
                    <summary>Show source phrasing</summary>
                    <p className="ji-details__body">{experience.raw}</p>
                  </details>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Architecture ───────────────────────────────────────── */}
      {job.architecture_topics?.length > 0 && (
        <div id="ji-sec-architecture" className="ji-card">
          <h2>Architecture & system-design topics</h2>
          <div className="ji-tag-list">
            {job.architecture_topics.map((t) => <span key={t} className="ji-tag">{t}</span>)}
          </div>
        </div>
      )}

      {/* ── Company Intelligence ───────────────────────────────── */}
      <div id="ji-sec-company">
        <CompanyIntelligenceCard company={company} />
      </div>

      {/* ── Resume signals (collapsible) ───────────────────────── */}
      {resumeRelevantKeywords.length > 0 && (
        <div id="ji-sec-resume" className="ji-card">
          <button
            type="button"
            className="ji-collapsible-header"
            onClick={() => setResumeOpen((v) => !v)}
            aria-expanded={resumeOpen}
          >
            <h2>Resume signals</h2>
            <span className="ji-collapsible-header__meta">
              {resumeRelevantKeywords.length} relevant term{resumeRelevantKeywords.length === 1 ? '' : 's'}
              <span className={`ji-chevron ${resumeOpen ? 'ji-chevron--open' : ''}`}>▸</span>
            </span>
          </button>
          {resumeOpen && (
            <>
              <div className="ji-tag-list">
                {resumeRelevantKeywords.map((k) => <span key={k} className="ji-tag ji-tag--muted">{k}</span>)}
              </div>
              {keywordTiers.raw?.length > 0 && (
                <details className="ji-details">
                  <summary>Show exact JD phrasing</summary>
                  <div className="ji-tag-list ji-details__body">
                    {keywordTiers.raw.map((k) => <span key={k} className="ji-tag">{k}</span>)}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}

      {/* ── Interview preparation signals ──────────────────────── */}
      {(foundations.length > 0 || design.length > 0 || stack.length > 0) && (
        <div id="ji-sec-interview" className="ji-card">
          <h2>Interview preparation signals</h2>
          <p className="ji-card__lead">
            Inferred from role requirements — not explicitly stated by the JD.
          </p>
          {stack.length > 0 && (
            <div className="ji-results__row">
              <h4>Application stack</h4>
              <div className="ji-tag-list">
                {stack.map((a) => <span key={a} className="ji-tag ji-tag--muted">{a}</span>)}
              </div>
            </div>
          )}
          {foundations.length > 0 && (
            <div className="ji-results__row">
              <h4>Technical foundations</h4>
              <div className="ji-tag-list">
                {foundations.map((a) => <span key={a} className="ji-tag ji-tag--muted">{a}</span>)}
              </div>
            </div>
          )}
          {design.length > 0 && (
            <div className="ji-results__row">
              <h4>Design & scale</h4>
              <div className="ji-tag-list">
                {design.map((a) => <span key={a} className="ji-tag ji-tag--muted">{a}</span>)}
              </div>
            </div>
          )}
          {interviewFocus.explicit?.length > 0 && (
            <div className="ji-results__row">
              <h4>Explicitly stated by the JD</h4>
              <div className="ji-tag-list">
                {interviewFocus.explicit.map((a) => <span key={a} className="ji-tag">{a}</span>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Raw JSON (debug) ────────────────────────────────────── */}
      <div className="ji-card">
        <button type="button" className="ji-results__raw-toggle" onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide raw JSON response' : 'Show raw JSON response'}
        </button>
        {showRaw && <pre className="ji-results__raw-json">{JSON.stringify(data, null, 2)}</pre>}
      </div>
    </div>
  )
}

export default JobIntelligenceResults