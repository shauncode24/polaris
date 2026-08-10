import { useMemo, useState } from 'react'
import './SkillGapResults.css'

const REQ_TYPE_LABEL = { required: 'Required', implicit: 'Implicit', nice_to_have: 'Nice to have' }
const REQ_TYPE_TONE = { required: 'required', implicit: 'implicit', nice_to_have: 'nice' }

// ---------------------------------------------------------------------------
// Lookups from job intelligence
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Shared sub-components
// ---------------------------------------------------------------------------
function ReqTypeBadge({ type }) {
  if (!type) return null
  return <span className={`sg-reqtype sg-reqtype--${REQ_TYPE_TONE[type] || 'nice'}`}>{REQ_TYPE_LABEL[type] || type}</span>
}

function ConfidenceBar({ confidence }) {
  const pct = Math.round(confidence * 100)
  const cls = pct >= 75 ? 'high' : pct >= 45 ? 'medium' : 'low'
  return (
    <span className={`sg-conf sg-conf--${cls}`}>
      {pct}% confidence
    </span>
  )
}

function barTierClass(pct) {
  if (pct >= 80) return 'sg-catbar__fill--strong'
  if (pct >= 60) return 'sg-catbar__fill--good'
  if (pct >= 40) return 'sg-catbar__fill--partial'
  return 'sg-catbar__fill--weak'
}

// ---------------------------------------------------------------------------
// Skill row components
// ---------------------------------------------------------------------------
function HaveItem({ item, reqType, enriched }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <li className="sg-skill">
      <div className="sg-skill__row">
        <span className="sg-skill__name">{item.skill.replace(/_/g, ' ')}</span>
        <ReqTypeBadge type={reqType} />
      </div>
      <ConfidenceBar confidence={item.confidence} />
      {item.explanation && <p className="sg-skill__desc">{item.explanation}</p>}
      {enriched?.category && <span className="sg-skill__category">{enriched.category}</span>}
      {item.evidence?.length > 0 && (
        <button type="button" className="sg-skill__toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide evidence' : `${item.evidence.length} evidence source${item.evidence.length === 1 ? '' : 's'}`}
        </button>
      )}
      {expanded && (
        <ul className="sg-skill__evidence">
          {item.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
      {item.confidence_flags?.length > 0 && <p className="sg-skill__flag">⚠ {item.confidence_flags[0]}</p>}
    </li>
  )
}

function PartialItem({ item, reqType, enriched }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <li className="sg-skill">
      <div className="sg-skill__row">
        <span className="sg-skill__name">{item.skill.replace(/_/g, ' ')}</span>
        <ReqTypeBadge type={reqType} />
      </div>
      <ConfidenceBar confidence={item.confidence} />
      {item.explanation && <p className="sg-skill__desc">{item.explanation}</p>}
      {item.reason && <p className="sg-skill__reason">{item.reason}</p>}
      {enriched?.category && <span className="sg-skill__category">{enriched.category}</span>}
      {item.evidence?.length > 0 && (
        <button type="button" className="sg-skill__toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide evidence' : `${item.evidence.length} evidence source${item.evidence.length === 1 ? '' : 's'}`}
        </button>
      )}
      {expanded && (
        <ul className="sg-skill__evidence">
          {item.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
    </li>
  )
}

function MissingItem({ item, reqType, enriched, priorityIndex }) {
  return (
    <li className="sg-skill sg-skill--missing">
      <div className="sg-skill__row">
        <span className="sg-skill__name">{item.skill.replace(/_/g, ' ')}</span>
        <ReqTypeBadge type={reqType} />
      </div>
      {priorityIndex != null && <span className="sg-priority">Priority gap #{priorityIndex + 1}</span>}
      {item.unmatched_explanation && <p className="sg-skill__desc">{item.unmatched_explanation}</p>}
      {enriched?.category && <span className="sg-skill__category">{enriched.category}</span>}
      {item.estimated_weeks > 0 && (
        <span className="sg-skill__effort">~{item.estimated_weeks}w effort</span>
      )}
    </li>
  )
}

// ---------------------------------------------------------------------------
// Category breakdown with expandable missing skills
// ---------------------------------------------------------------------------
function CategoryRow({ c }) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(c.score * 100)
  return (
    <div className="sg-catbar">
      <div className="sg-catbar__main">
        <span className="sg-catbar__label">{c.category}</span>
        <div className="sg-catbar__track">
          <div className={`sg-catbar__fill ${barTierClass(pct)}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="sg-catbar__pct">{pct}%</span>
        <span className="sg-catbar__matched">{c.matched_skills} matched</span>
        {c.missing_skills?.length > 0 && (
          <button type="button" className="sg-catbar__toggle" onClick={() => setExpanded((v) => !v)}>
            {c.missing_skills.length} gap{c.missing_skills.length === 1 ? '' : 's'} {expanded ? '▴' : '▾'}
          </button>
        )}
      </div>
      {expanded && c.missing_skills?.length > 0 && (
        <div className="sg-catbar__gaps">
          {c.missing_skills.map((s) => (
            <span key={s} className="sg-catbar__gap-chip">{s.replace(/_/g, ' ')}</span>
          ))}
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

  function matchesFilters(skillName, tier) {
    if (statusFilter !== 'all' && statusFilter !== tier) return false
    const reqType = canonicalSkillsMap[skillName]
    if (typeFilter !== 'all' && reqType !== typeFilter) return false
    if (search && !skillName.toLowerCase().includes(search.toLowerCase())) return false
    return true
  }

  const have = (report.have || []).filter((i) => matchesFilters(i.skill, 'have'))
  const partial = (report.partial || []).filter((i) => matchesFilters(i.skill, 'partial'))
  const missing = (report.missing || [])
    .filter((i) => matchesFilters(i.skill, 'missing'))
    .sort((a, b) => (priorityIndexBySkill[a.skill] ?? 999) - (priorityIndexBySkill[b.skill] ?? 999))

  // Unfiltered top priority gaps for the summary strip
  const topPriorityGaps = [...(report.missing || [])]
    .sort((a, b) => (priorityIndexBySkill[a.skill] ?? 999) - (priorityIndexBySkill[b.skill] ?? 999))
    .slice(0, 3)

  const seniority = job.seniority_signal || {}
  const quality = job.extraction_quality || {}
  const anyFilterActive = search || typeFilter !== 'all' || statusFilter !== 'all'

  // Counts for status tabs
  const haveTotal = (report.have || []).length
  const partialTotal = (report.partial || []).length
  const missingTotal = (report.missing || []).length

  return (
    <div className="sg-results">
      {/* Degraded notice */}
      {degraded && (
        <p className="sg-notice">
          The narrative summary used a simplified fallback — the underlying skill comparison data is still accurate.
        </p>
      )}

      {/* Header */}
      <div className="sg-header">
        <div className="sg-header__main">
          <h2>{job.role || 'Untitled role'}{job.company ? ` at ${job.company}` : ''}</h2>
          <div className="sg-header__badges">
            {seniority.level && seniority.level !== 'unspecified' && (
              <span className="sg-badge">{seniority.level}</span>
            )}
            {quality.label && <span className="sg-badge sg-badge--muted">{quality.label}-confidence extraction</span>}
          </div>
        </div>
        <div className="sg-header__actions">
          <button type="button" className="sg-action-btn" onClick={onRegenerate}>↻ Re-analyze</button>
        </div>
      </div>

      {/* Match + Coverage */}
      <div className="sg-coverage-grid">
        <div className="sg-match-card">
          <span className="sg-match-label">Overall match</span>
          <span className="sg-match-value">{Math.round(match.percentage)}%</span>
          <span className={`sg-match-tag sg-match-tag--${match.percentage >= 75 ? 'strong' : match.percentage >= 50 ? 'good' : 'weak'}`}>
            {match.label}
          </span>
        </div>
        <div className="sg-coverage-card">
          <div className="sg-coverage-row">
            <div className="sg-coverage-stat">
              <strong>{match.required_matched}</strong>
              <span>Required / implicit coverage</span>
            </div>
            <div className="sg-coverage-stat">
              <strong>{match.nice_to_have_matched}</strong>
              <span>Nice-to-have coverage</span>
            </div>
            <div className="sg-coverage-stat">
              <strong>{match.matched_requirements}</strong>
              <span>Total requirements matched</span>
            </div>
          </div>
        </div>
      </div>

      {/* Priority gap strip */}
      {topPriorityGaps.length > 0 && (
        <div className="sg-card">
          <h3>Highest priority gaps</h3>
          <p className="sg-card__lead">Most important missing skills based on requirement type and role weight</p>
          <div className="sg-gap-chips">
            {topPriorityGaps.map((m) => (
              <div key={m.skill} className="sg-gap-chip">
                <span className="sg-gap-chip__name">{m.skill.replace(/_/g, ' ')}</span>
                <ReqTypeBadge type={canonicalSkillsMap[m.skill]} />
                {m.estimated_weeks > 0 && <span className="sg-gap-chip__effort">~{m.estimated_weeks}w</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Narrative summary */}
      {analysis.executive_summary && (
        <div className="sg-card">
          <h3>Match summary</h3>
          <p>{analysis.executive_summary}</p>
          {analysis.role_focus?.length > 0 && (
            <>
              <p className="sg-card__lead sg-card__lead--spaced">What this role emphasises</p>
              <div className="sg-tag-list">
                {analysis.role_focus.map((f) => <span key={f} className="sg-tag">{f}</span>)}
              </div>
            </>
          )}
        </div>
      )}

      {/* Strengths & risks */}
      {(analysis.strengths?.length > 0 || analysis.risks?.length > 0) && (
        <div className="sg-grid-2">
          {analysis.strengths?.length > 0 && (
            <div className="sg-card">
              <h3>Strengths</h3>
              <ul className="sg-check-list">{analysis.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}</ul>
            </div>
          )}
          {analysis.risks?.length > 0 && (
            <div className="sg-card">
              <h3>Gaps</h3>
              <ul className="sg-warn-list">{analysis.risks.map((r, i) => <li key={i}>⚠ {r}</li>)}</ul>
            </div>
          )}
        </div>
      )}

      {/* Skill evidence — filters + columns */}
      <div className="sg-card">
        <div className="sg-filter-row">
          <input
            type="text"
            className="sg-search"
            placeholder="Search skills…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <div className="sg-filter-group">
            <div className="sg-filter-tabs">
              {[
                ['all', 'All'],
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
        </div>

        <div className="sg-columns">
          {statusFilter !== 'partial' && statusFilter !== 'missing' && (
            <div className="sg-column sg-column--have">
              <h4><span className="sg-dot sg-dot--have" /> Have <span className="sg-count">{have.length}</span></h4>
              {have.length === 0 ? (
                <p className="sg-empty">{anyFilterActive ? 'No skills match this filter.' : 'No confidently verified skills matched this role.'}</p>
              ) : (
                <ul>{have.map((h) => <HaveItem key={h.skill} item={h} reqType={canonicalSkillsMap[h.skill]} enriched={enrichedBySkill[h.skill]} />)}</ul>
              )}
            </div>
          )}
          {statusFilter !== 'have' && statusFilter !== 'missing' && (
            <div className="sg-column sg-column--partial">
              <h4><span className="sg-dot sg-dot--partial" /> Partial <span className="sg-count">{partial.length}</span></h4>
              {partial.length === 0 ? (
                <p className="sg-empty">{anyFilterActive ? 'No skills match this filter.' : 'No partially-evidenced skills.'}</p>
              ) : (
                <ul>{partial.map((p) => <PartialItem key={p.skill} item={p} reqType={canonicalSkillsMap[p.skill]} enriched={enrichedBySkill[p.skill]} />)}</ul>
              )}
            </div>
          )}
          {statusFilter !== 'have' && statusFilter !== 'partial' && (
            <div className="sg-column sg-column--missing">
              <h4><span className="sg-dot sg-dot--missing" /> Missing <span className="sg-count">{missing.length}</span></h4>
              {missing.length === 0 ? (
                <p className="sg-empty">{anyFilterActive ? 'No skills match this filter.' : 'Nothing missing — your profile covers this role fully.'}</p>
              ) : (
                <ul>
                  {missing.map((m) => (
                    <MissingItem
                      key={m.skill}
                      item={m}
                      reqType={canonicalSkillsMap[m.skill]}
                      enriched={enrichedBySkill[m.skill]}
                      priorityIndex={priorityIndexBySkill[m.skill]}
                    />
                  ))}
                </ul>
              )}
            </div>
          )}
          {statusFilter !== 'all' && have.length === 0 && partial.length === 0 && missing.length === 0 && (
            <p className="sg-empty sg-empty--full">No skills match this filter.</p>
          )}
        </div>
      </div>

      {/* Category breakdown */}
      {categories?.length > 0 && (
        <div className="sg-card">
          <h3>Category breakdown</h3>
          <p className="sg-card__lead">Match score by technical domain — expand any row to see the missing skills</p>
          <div className="sg-catbar-list">
            {categories.map((c) => <CategoryRow key={c.category} c={c} />)}
          </div>
        </div>
      )}
    </div>
  )
}

export default SkillGapResults