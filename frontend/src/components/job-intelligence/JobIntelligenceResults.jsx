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
  internship_or_project: 'Internship / project experience accepted',
  professional: 'Professional experience required',
  not_specified: '',
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
          <span key={s.canonical} className="ji-skill-chip" title={s.evidence || undefined}>
            {s.canonical.replace(/_/g, ' ')}
            {PROFICIENCY_LABELS[s.proficiency_signal] && (
              <span className="ji-skill-chip__proficiency">{PROFICIENCY_LABELS[s.proficiency_signal]}</span>
            )}
            {s.requirement_type === 'implicit' && (
              <span className={`ji-skill-chip__confidence ji-skill-chip__confidence--${s.confidence}`}>
                inferred · {s.confidence}
              </span>
            )}
            <span className="ji-skill-chip__category">{s.category}</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function RoleIdentityRow({ label, value }) {
  if (!value) return null
  return (
    <div className="ji-identity-row">
      <span className="ji-identity-row__label">{label}</span>
      <span className="ji-identity-row__value">{value}</span>
    </div>
  )
}

function JobIntelligenceResults({ data }) {
  const [showRaw, setShowRaw] = useState(false)
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

  const hasIdentityDetail =
    identity.designation || identity.grade || identity.function ||
    identity.department || identity.location || identity.reports_to || identity.employment_type

  const hasQualifications =
    qualifications.education?.length > 0 || qualifications.eligibility?.length > 0 || !!experience

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

      {/* Role identity */}
      {hasIdentityDetail && (
        <div className="ji-results__card">
          <h2>Role identity</h2>
          <div className="ji-identity-grid">
            <RoleIdentityRow label="Designation" value={identity.designation} />
            <RoleIdentityRow label="Grade" value={identity.grade} />
            <RoleIdentityRow label="Function" value={identity.function} />
            <RoleIdentityRow label="Department" value={identity.department} />
            <RoleIdentityRow label="Location" value={identity.location} />
            <RoleIdentityRow label="Reports to" value={identity.reports_to} />
            <RoleIdentityRow label="Employment type" value={identity.employment_type} />
          </div>
          {identity.designation && identity.grade && (
            <p className="ji-results__card-lead">
              Designation and grade are shown separately from seniority — a "{identity.grade}" grade
              doesn't necessarily mean a senior engineering level.
            </p>
          )}
        </div>
      )}

      {/* Job purpose */}
      {job.job_purpose && (
        <div className="ji-results__card">
          <h2>Why this role exists</h2>
          <p>{job.job_purpose}</p>
        </div>
      )}

      {/* Responsibilities */}
      {job.responsibilities?.length > 0 && (
        <div className="ji-results__card">
          <h2>What you'll actually do</h2>
          <ul className="ji-results__evidence-list">
            {job.responsibilities.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      )}

      {/* Capabilities */}
      {job.capabilities?.length > 0 && (
        <div className="ji-results__card">
          <h2>Capabilities expected</h2>
          <p className="ji-results__card-lead">Action-oriented — distinct from the architecture concepts below</p>
          <div className="ji-tag-list">
            {job.capabilities.map((c, i) => <span key={i} className="ji-tag">{c}</span>)}
          </div>
        </div>
      )}

      {/* Qualifications & eligibility */}
      {hasQualifications && (
        <div className="ji-results__card">
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
              <h4>Eligibility requirements</h4>
              <ul className="ji-results__evidence-list">
                {qualifications.eligibility.map((e, i) => (
                  <li key={i}>{e.requirement}{e.detail ? ` — ${e.detail}` : ''}</li>
                ))}
              </ul>
            </div>
          )}
          {experience && (
            <div className="ji-results__row">
              <h4>Experience</h4>
              <p>{experience.raw || 'Stated in the job description'}</p>
              <div className="ji-tag-list">
                {EXPERIENCE_TYPE_LABELS[experience.experience_type] && (
                  <span className="ji-tag">{EXPERIENCE_TYPE_LABELS[experience.experience_type]}</span>
                )}
                {experience.domain && (
                  <span className="ji-tag ji-tag--muted">{experience.domain.replace(/_/g, ' ')}</span>
                )}
                {experience.minimum_years != null && (
                  <span className="ji-tag ji-tag--muted">{experience.minimum_years}+ years stated</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

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
        <p className="ji-results__card-lead">
          Includes both named technologies and explicitly stated processes/practices (e.g. git workflows,
          design patterns) — not just product names
        </p>
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
      {resumeRelevantKeywords.length > 0 && (
        <div className="ji-results__card">
          <h2>Resume keywords</h2>
          <p className="ji-results__card-lead">Literal terms worth surfacing on a resume for this role</p>
          <div className="ji-tag-list">
            {resumeRelevantKeywords.map((k) => <span key={k} className="ji-tag ji-tag--muted">{k}</span>)}
          </div>
          {keywordTiers.raw?.length > 0 && (
            <details className="ji-results__keyword-detail">
              <summary>Show exact JD phrasing</summary>
              <div className="ji-tag-list">
                {keywordTiers.raw.map((k) => <span key={k} className="ji-tag">{k}</span>)}
              </div>
            </details>
          )}
        </div>
      )}

      {/* Interview focus areas */}
      {(interviewFocus.explicit?.length > 0 || interviewFocus.inferred?.length > 0) && (
        <div className="ji-results__card">
          <h2>Interview focus areas</h2>
          {interviewFocus.explicit?.length > 0 && (
            <div className="ji-results__row">
              <h4>Explicitly stated / directly required</h4>
              <div className="ji-tag-list">
                {interviewFocus.explicit.map((a) => <span key={a} className="ji-tag">{a}</span>)}
              </div>
            </div>
          )}
          {interviewFocus.inferred?.length > 0 && (
            <div className="ji-results__row">
              <h4>Inferred — not explicitly stated in the JD</h4>
              <div className="ji-tag-list">
                {interviewFocus.inferred.map((a) => <span key={a} className="ji-tag ji-tag--muted">{a}</span>)}
              </div>
            </div>
          )}
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