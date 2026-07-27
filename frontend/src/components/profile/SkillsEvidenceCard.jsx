import Card from '../common/Card'
import { IconTarget } from '../icons/Icons'
import './ProfileSectionCard.css'

// Group skills from resume data by category if available, else by confidence
function buildSkillGroups(resumeResult) {
  if (!resumeResult) return []

  const rawSkills = resumeResult.skills

  // Backend returns skills as { "skill_name": { confidence, evidence } }
  if (rawSkills && typeof rawSkills === 'object' && !Array.isArray(rawSkills)) {
    const high = [], medium = [], low = []
    for (const [name, data] of Object.entries(rawSkills)) {
      const conf = data.confidence ?? 0
      const sources = data.evidence?.length ?? 0
      const item = { name, confidence: conf, sources }
      if (conf >= 0.6) high.push(item)
      else if (conf >= 0.3) medium.push(item)
      else low.push(item)
    }
    const groups = []
    if (high.length > 0) groups.push({ label: 'High confidence', items: high.sort((a, b) => b.confidence - a.confidence) })
    if (medium.length > 0) groups.push({ label: 'Medium confidence', items: medium.sort((a, b) => b.confidence - a.confidence) })
    if (low.length > 0) groups.push({ label: 'Low confidence', items: low.sort((a, b) => b.confidence - a.confidence) })
    return groups
  }

  // Array format (future-proof)
  const skills = Array.isArray(rawSkills) ? rawSkills : []
  if (skills.length === 0) return []

  // Group by category if present, else a single group
  const groupMap = {}
  for (const skill of skills) {
    const cat = skill.category || 'General'
    if (!groupMap[cat]) groupMap[cat] = []
    groupMap[cat].push(skill)
  }

  return Object.entries(groupMap).map(([label, items]) => ({ label, items }))
}

function confidenceLabel(confidence) {
  if (!confidence) return 'medium'
  const val = typeof confidence === 'number' ? confidence : 0
  if (val >= 0.7) return 'high'
  if (val >= 0.4) return 'medium'
  return 'low'
}

function confidenceText(confidence) {
  const label = confidenceLabel(confidence)
  return label.charAt(0).toUpperCase() + label.slice(1)
}

function SkillRow({ skill }) {
  const conf = confidenceLabel(skill.confidence)
  const sources = typeof skill.sources === 'number'
    ? skill.sources
    : (Array.isArray(skill.sources) ? skill.sources.length : (skill.evidence_count ?? 1))

  return (
    <div className="psc__skill-row">
      <span className="psc__skill-name">{skill.name || skill.skill}</span>
      <div className="psc__skill-meta">
        <span className={`psc__confidence psc__confidence--${conf}`}>
          {confidenceText(skill.confidence)}
        </span>
        <span className="psc__source-count">{sources} source{sources !== 1 ? 's' : ''}</span>
      </div>
    </div>
  )
}

// Determine if any skill needs more evidence
function needsMoreEvidence(groups) {
  return groups.some((g) => g.label === 'Low confidence' || g.items.some((s) => confidenceLabel(s.confidence) === 'low'))
}

function SkillsEvidenceCard({ results }) {
  const groups = buildSkillGroups(results?.resume)
  const hasWarning = groups.length > 0 && needsMoreEvidence(groups)

  // If no structured skills, fall back to high/medium/low counts from summary
  const summary = results?.resume
  const hasAnything = groups.length > 0 || summary?.skills_processed

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconTarget size={16} /></span>
          <h3 className="psc__title">Skills and evidence</h3>
        </div>
        <button type="button" className="psc__header-link">Evidence model</button>
      </div>

      {hasWarning && (
        <div className="psc__skills-warning">
          <div className="psc__skills-warning-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" /><path d="M12 8v4M12 16h.01" />
            </svg>
            Needs more evidence
          </div>
          <div className="psc__skills-warning-body">
            Some skills have low confidence — add outcomes, a project, or a source connection rather than editing a score.
          </div>
        </div>
      )}

      {!hasAnything ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No skills detected yet — upload a resume to get started.</span>
        </div>
      ) : groups.length > 0 ? (
        groups.map((g) => (
          <div key={g.label} className="psc__skill-group">
            <div className="psc__skill-group-label">{g.label}</div>
            {g.items.map((s, i) => (
              <SkillRow key={s.name || s.skill || i} skill={s} />
            ))}
          </div>
        ))
      ) : (
        // Fallback: show summary as raw counts
        <div className="psc__body">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
            {[
              { label: 'High confidence', value: summary?.skills_high_confidence ?? 0, conf: 'high' },
              { label: 'Medium', value: summary?.skills_medium_confidence ?? 0, conf: 'medium' },
              { label: 'Low', value: summary?.skills_low_confidence ?? 0, conf: 'low' },
            ].map((item) => (
              <div key={item.label} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ink)' }}>{item.value}</div>
                <div style={{ fontSize: 12, color: 'var(--text-soft)', marginTop: 2 }}>{item.label}</div>
              </div>
            ))}
          </div>
          <p style={{ fontSize: 12.5, color: 'var(--text-soft)', marginTop: 8 }}>
            Detailed skill breakdown becomes available after the backend returns per-skill data.
          </p>
        </div>
      )}
    </Card>
  )
}

export default SkillsEvidenceCard
