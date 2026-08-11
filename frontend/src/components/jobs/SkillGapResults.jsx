// frontend/src/components/jobs/SkillGapResults.jsx
import { useMemo, useState } from 'react'
import './SkillGapResults.css'

const REQ_TYPE_LABEL = { required: 'Required', implicit: 'Implicit', nice_to_have: 'Nice to have' }
const REQ_TYPE_TONE = { required: 'required', implicit: 'implicit', nice_to_have: 'nice' }

// Canonical skill names come through as snake_case ("full_stack_development",
// "aws"). Title-case each word, but keep known acronyms upper-cased instead
// of "Aws" / "Dsa" leaking into the UI.
const ACRONYMS = new Set([
  'aws', 'api', 'ui', 'ux', 'sql', 'ai', 'ml', 'ci', 'cd', 'gcp', 'json',
  'html', 'css', 'js', 'ts', 'ec2', 's3', 'iam', 'rest', 'grpc', 'http',
  'https', 'dsa', 'oop', 'tcp', 'ip', 'dns', 'cli', 'sdk', 'jwt', 'orm',
  'crud', 'saas', 'paas', 'iaas', 'oauth',
])

function normalizeSkillName(raw) {
  if (!raw) return ''
  return raw
    .split('_')
    .map((word) => {
      const lower = word.toLowerCase()
      return ACRONYMS.has(lower) ? lower.toUpperCase() : lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}

function useSkillLookups(jobIntelligence) {
  return useMemo(() => {
    const enrichedBySkill = {}
    for (const group of [
      jobIntelligence.enriched_required_skills,
      jobIntelligence.enriched_implicit_skills,
      jobIntelligence.enriched_nice_to_have,
    ]) {
      for (const s of group || []) {
        if (!enrichedBySkill[s.canonical]) enrichedBySkill[s.canonical] = s
      }
    }
    return { enrichedBySkill, canonicalSkillsMap: jobIntelligence.canonical_skills_map || {} }
  }, [jobIntelligence])
}

// Flattens have/partial/missing into one sorted list so the UI can render
// a single table instead of three columns that are almost always
// wildly uneven in length.
function useCombinedSkills(report, canonicalSkillsMap, enrichedBySkill, priorityIndexBySkill) {
  return useMemo(() => {
    const rows = []

    for (const h of report.have || []) {
      rows.push({
        status: 'have',
        skill: h.skill,
        confidence: h.confidence,
        explanation: h.explanation,
        evidence: h.evidence || [],
        flags: h.confidence_flags || [],
        reqType: canonicalSkillsMap[h.skill],
        category: enrichedBySkill[h.skill]?.category,
      })
    }
    for (const p of report.partial || []) {
      rows.push({
        status: 'partial',
        skill: p.skill,
        confidence: p.confidence,
        explanation: p.explanation,
        reason: p.reason,
        evidence: p.evidence || [],
        reqType: canonicalSkillsMap[p.skill],
        category: enrichedBySkill[p.skill]?.category,
      })
    }
    for (const m of report.missing || []) {
      rows.push({
        status: 'missing',
        skill: m.skill,
        unmatchedExplanation: m.unmatched_explanation,
        estimatedWeeks: m.estimated_weeks,
        priorityIndex: priorityIndexBySkill[m.skill],
        reqType: canonicalSkillsMap[m.skill],
        category: enrichedBySkill[m.skill]?.category,
      })
    }

    const statusOrder = { have: 0, partial: 1, missing: 2 }
    rows.sort((a, b) => {
      if (statusOrder[a.status] !== statusOrder[b.status]) return statusOrder[a.status] - statusOrder[b.status]
      if (a.status === 'missing') return (a.priorityIndex ?? 999) - (b.priorityIndex ?? 999)
      return (b.confidence ?? 0) - (a.confidence ?? 0)
    })

    return rows
  }, [report, canonicalSkillsMap, enrichedBySkill, priorityIndexBySkill])
}

function ReqTypeBadge({ type }) {
  if (!type) return null
  return <span className={`sg-reqtype sg-reqtype--${REQ_TYPE_TONE[type] || 'nice'}`}>{REQ_TYPE_LABEL[type] || type}</span>
}

function StatusIcon({ status }) {
  if (status === 'have') return <span className="sg-status-icon sg-status-icon--have">✓</span>
  if (status === 'partial') return <span className="sg-status-icon sg-status-icon--partial">±</span>
  return <span className="sg-status-icon sg-status-icon--missing">✕</span>
}

function barTierClass(pct) {
  if (pct >= 80) return 'sg-catbar__fill--strong'
  if (pct >= 60) return 'sg-catbar__fill--good'
  if (pct >= 40) return 'sg-catbar__fill--partial'
  return 'sg-catbar__fill--weak'
}

// ---------------------------------------------------------------------------
// Skill row — progressive disclosure: one line by default, expands for
// evidence / explanation instead of showing everything at once.
// ---------------------------------------------------------------------------
function SkillRow({ row }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetail = (row.evidence && row.evidence.length > 0) || row.explanation || row.reason || row.unmatchedExplanation

  return (
    <li className={`sg-row sg-row--${row.status}`}>
      <button
        type="button"
        className={`sg-row__header ${hasDetail ? '' : 'sg-row__header--static'}`}
        onClick={() => hasDetail && setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <StatusIcon status={row.status} />
        <span className="sg-row__name">{normalizeSkillName(row.skill)}</span>
        <ReqTypeBadge type={row.reqType} />

        {row.status === 'missing' && row.priorityIndex != null && (
          <span className="sg-row__priority">Priority #{row.priorityIndex + 1}</span>
        )}
        {(row.status === 'have' || row.status === 'partial') && row.confidence != null && (
          <span
            className={`sg-row__confidence sg-row__confidence--${
              row.confidence >= 0.75 ? 'high' : row.confidence >= 0.45 ? 'medium' : 'low'
            }`}
          >
            {Math.round(row.confidence * 100)}%
          </span>
        )}
        {row.status === 'missing' && row.estimatedWeeks > 0 && (
          <span className="sg-row__effort">~{row.estimatedWeeks}w</span>
        )}

        {hasDetail && <span className={`sg-row__chevron ${expanded ? 'sg-row__chevron--open' : ''}`}>▾</span>}
      </button>

      {expanded && (
        <div className="sg-row__detail">
          {row.explanation && <p>{row.explanation}</p>}
          {row.status === 'partial' && row.reason && <p className="sg-row__reason">{row.reason}</p>}
          {row.unmatchedExplanation && <p>{row.unmatchedExplanation}</p>}
          {row.evidence?.length > 0 && (
            <ul className="sg-row__evidence">
              {row.evidence.map((e, i) => <li key={i}>{e}</li>)}
            </ul>
          )}
          {row.flags?.length > 0 && <p className="sg-row__flag">⚠ {row.flags[0]}</p>}
        </div>
      )}
    </li>
  )
}

// ---------------------------------------------------------------------------
// Category breakdown — leads with coverage count (per audit note: "0%"
// reads as catastrophic on a 1-2 skill category), expands to the actual
// skills behind that number instead of just the missing-skill chip list.
// ---------------------------------------------------------------------------
function CategoryRow({ c, combinedSkills }) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(c.score * 100)
  const categorySkills = combinedSkills.filter((s) => s.category === c.category)

  return (
    <div className="sg-catrow">
      <button type="button" className="sg-catrow__header" onClick={() => setExpanded((v) => !v)} aria-expanded={expanded}>
        <span className="sg-catrow__label">{c.category}</span>
        <span className="sg-catrow__matched">{c.matched_skills} matched</span>
        <div className="sg-catrow__track">
          <div className={`sg-catbar__fill ${barTierClass(pct)}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="sg-catrow__pct">{pct}%</span>
        <span className={`sg-catrow__chevron ${expanded ? 'sg-catrow__chevron--open' : ''}`}>▾</span>
      </button>

      {expanded && (
        <div className="sg-catrow__body">
          {categorySkills.length === 0 ? (
            <p className="sg-empty">No individual skill detail available for this category.</p>
          ) : (
            categorySkills.map((s) => (
              <div key={s.skill} className={`sg-catrow__skill sg-catrow__skill--${s.status}`}>
                <StatusIcon status={s.status} />
                <span>{normalizeSkillName(s.skill)}</span>
                {s.status !== 'missing' && s.confidence != null && (
                  <span className="sg-catrow__skill-conf">{Math.round(s.confidence * 100)}%</span>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
function SkillGapResults({ data, onRegenerate }) {
  const {
    job_intelligence: job,
    report,
    category_breakdown: categories,
    overall_match: match,
    analysis,
    analysis_degraded: degraded,
  } = data

  const { enrichedBySkill, canonicalSkillsMap } = useSkillLookups(job)

  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all') // all | required | implicit | nice_to_have
  const [statusFilter, setStatusFilter] = useState('all') // all | have | partial | missing

  const priorityIndexBySkill = useMemo(() => {
    const map = {}
    ;(report.priority_order || []).forEach((s, i) => { map[s] = i })
    return map
  }, [report.priority_order])

  const combinedSkills = useCombinedSkills(report, canonicalSkillsMap, enrichedBySkill, priorityIndexBySkill)

  const filteredSkills = combinedSkills.filter((row) => {
    if (statusFilter !== 'all' && statusFilter !== row.status) return false
    if (typeFilter !== 'all' && row.reqType !== typeFilter) return false
    if (search && !row.skill.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const topPriorityGaps = [...(report.missing || [])]
    .sort((a, b) => (priorityIndexBySkill[a.skill] ?? 999) - (priorityIndexBySkill[b.skill] ?? 999))
    .slice(0, 3)

  const seniority = job.seniority_signal || {}
  const quality = job.extraction_quality || {}
  const anyFilterActive = Boolean(search) || typeFilter !== 'all' || statusFilter !== 'all'

  const haveTotal = (report.have || []).length
  const partialTotal = (report.partial || []).length
  const missingTotal = (report.missing || []).length

  return (
    <div className="sg-results">
      {degraded && (
        <p className="sg-notice">
          The narrative summary used a simplified fallback — the underlying skill comparison data is still accurate.
        </p>
      )}

      {/* Header — role/company as the primary heading; extraction quality
          and re-analyze are secondary, not competing for attention. */}
      <div className="sg-header">
        <div className="sg-header__main">
          <h2>{job.role || 'Untitled role'}{job.company ? ` at ${job.company}` : ''}</h2>
          {seniority.level && seniority.level !== 'unspecified' && (
            <span className="sg-badge">{seniority.level}</span>
          )}
        </div>
        <div className="sg-header__actions">
          {quality.label && <span className="sg-header__meta">{quality.label}-confidence extraction</span>}
          <button type="button" className="sg-action-btn" onClick={onRegenerate}>↻ Re-analyze</button>
        </div>
      </div>

      {/* Match overview — score, required/nice-to-have coverage, and a
          compact top-gaps strip. Total-requirements-matched dropped as
          redundant with required + nice-to-have. */}
      <div className="sg-overview">
        <div className="sg-match-card">
          <span className="sg-match-label">Overall match</span>
          <span className="sg-match-value">{Math.round(match.percentage)}%</span>
          <span className={`sg-match-tag sg-match-tag--${match.percentage >= 75 ? 'strong' : match.percentage >= 50 ? 'good' : 'weak'}`}>
            {match.label}
          </span>
        </div>

        <div className="sg-overview__right">
          <div className="sg-coverage-row">
            <div className="sg-coverage-stat">
              <strong>{match.required_matched}</strong>
              <span>Required / implicit matched</span>
            </div>
            <div className="sg-coverage-stat">
              <strong>{match.nice_to_have_matched}</strong>
              <span>Nice-to-have matched</span>
            </div>
          </div>

          {topPriorityGaps.length > 0 && (
            <div className="sg-top-gaps">
              <span className="sg-top-gaps__label">Top gaps</span>
              <div className="sg-top-gaps__list">
                {topPriorityGaps.map((m, i) => (
                  <span key={m.skill} className="sg-top-gaps__chip">
                    <strong>#{i + 1}</strong> {normalizeSkillName(m.skill)}
                    {m.estimated_weeks > 0 && <em>~{m.estimated_weeks}w</em>}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Match summary — narrative + role emphasis only. Strengths/Gaps
          list removed: it just previewed the skill table below. */}
      {analysis.executive_summary && (
        <div className="sg-card">
          <p className="sg-summary">{analysis.executive_summary}</p>
          {analysis.role_focus?.length > 0 && (
            <div className="sg-tag-list">
              {analysis.role_focus.map((f) => <span key={f} className="sg-tag">{f}</span>)}
            </div>
          )}
        </div>
      )}

      {/* Skill analysis — one filterable, expandable list instead of three
          uneven columns. */}
      <div className="sg-card">
        <div className="sg-filter-row">
          <h3>Skill analysis</h3>
          <input
            type="text"
            className="sg-search"
            placeholder="Search skills…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="sg-filter-tabs-row">
          <div className="sg-filter-tabs">
            {[
              ['all', `All (${haveTotal + partialTotal + missingTotal})`],
              ['have', `Have (${haveTotal})`],
              ['partial', `Partial (${partialTotal})`],
              ['missing', `Missing (${missingTotal})`],
            ].map(([val, label]) => (
              <button
                key={val}
                type="button"
                className={`sg-filter-tab ${statusFilter === val ? 'sg-filter-tab--active' : ''}`}
                onClick={() => setStatusFilter(val)}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="sg-filter-tabs sg-filter-tabs--type">
            {['all', 'required', 'implicit', 'nice_to_have'].map((t) => (
              <button
                key={t}
                type="button"
                className={`sg-filter-tab ${typeFilter === t ? 'sg-filter-tab--active' : ''}`}
                onClick={() => setTypeFilter(t)}
              >
                {t === 'all' ? 'Any type' : REQ_TYPE_LABEL[t]}
              </button>
            ))}
          </div>
        </div>

        {filteredSkills.length === 0 ? (
          <p className="sg-empty sg-empty--full">
            {anyFilterActive ? 'No skills match this filter.' : 'No skill data available.'}
          </p>
        ) : (
          <ul className="sg-row-list">
            {filteredSkills.map((row) => <SkillRow key={row.skill} row={row} />)}
          </ul>
        )}
      </div>

      {/* Category breakdown — leads with matched count, expands to the
          actual skills behind each category. */}
      {categories?.length > 0 && (
        <div className="sg-card">
          <h3>Category breakdown</h3>
          <p className="sg-card__lead">Match by technical domain — expand a category to see individual skills</p>
          <div className="sg-catrow-list">
            {categories.map((c) => <CategoryRow key={c.category} c={c} combinedSkills={combinedSkills} />)}
          </div>
        </div>
      )}
    </div>
  )
}

export default SkillGapResults