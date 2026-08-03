// frontend/src/components/identity/IdentityInsights.jsx
import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './IdentityInsights.css'

const SOURCE_LABELS = {
  resume: 'Resume',
  github: 'GitHub',
  leetcode: 'LeetCode',
  claim_audit: 'Claim Audit',
  job_descriptions: 'Job Descriptions',
}

function InsightRow({ title, summary, tone = 'neutral', children }) {
  const [open, setOpen] = useState(false)
  if (!children) {
    return (
      <div className="insights__row">
        <span className={`insights__row-title insights__row-title--${tone}`}>{title}</span>
        <span className="insights__row-summary">{summary}</span>
      </div>
    )
  }
  return (
    <div className="insights__row">
      <button type="button" className="insights__row-header" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span className={`insights__row-title insights__row-title--${tone}`}>{title}</span>
        <span className="insights__row-summary">{summary}</span>
        <span className="insights__row-toggle">{open ? 'Hide' : 'View'}</span>
      </button>
      {open && <div className="insights__row-body">{children}</div>}
    </div>
  )
}

// Consolidates what used to be four separate, always-open panels
// (Coverage Timeline, Claim Freshness, Source Freshness, and no prior
// "why" section at all) into one collapsed-by-default, scannable block.
// Each row shows only a conclusion; the underlying data — none of it
// new, all of it already returned by GET /identity — is one click away.
function IdentityInsights({ facts, contradictions = [] }) {
  const coverageGaps = facts?.coverage_gaps || {}
  const githubGaps = coverageGaps.github_gaps || []
  const leetcodeGaps = coverageGaps.leetcode_gaps || []
  const certificateGaps = coverageGaps.certificate_gaps || []
  const projectSuggestions = coverageGaps.project_suggestions || []
  const timelineNotes = facts?.timeline_plausibility_notes || []
  const coverageCount = githubGaps.length + leetcodeGaps.length + certificateGaps.length

  const claimRiskDetails = facts?.claim_risk_details || []

  const sourceFreshness = facts?.source_freshness || {}
  const needsAttention = Object.entries(sourceFreshness).filter(
    ([, info]) => !info.connected || info.is_stale
  )

  const topSkills = facts?.top_skills || []

  const hasAny =
    coverageCount > 0 ||
    timelineNotes.length > 0 ||
    claimRiskDetails.length > 0 ||
    Object.keys(sourceFreshness).length > 0 ||
    topSkills.length > 0 ||
    contradictions.length > 0

  if (!hasAny) return null

  return (
    <CollapsibleSection title="Identity Insights" defaultOpen={false} subtitle="Coverage, claims, freshness & evidence">
      <div className="insights">
        {contradictions.length > 0 && (
          <InsightRow title="Contradictions Polaris Found" summary={`${contradictions.length} item(s)`} tone="warn">
            <ul className="insights__list">
              {contradictions.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          </InsightRow>
        )}

        {(coverageCount > 0 || timelineNotes.length > 0 || projectSuggestions.length > 0) && (
          <InsightRow
            title="Coverage Issues"
            summary={`${coverageCount} skill(s) evidenced elsewhere, missing from resume${timelineNotes.length ? ` · ${timelineNotes.length} timeline note(s)` : ''}`}
            tone="gap"
          >
            {githubGaps.length > 0 && (
              <div className="insights__sublist">
                <span className="insights__sublist-title">Evidenced on GitHub</span>
                <ul className="insights__list">
                  {githubGaps.map((g, i) => <li key={i}><strong>{g.skill}</strong> — {g.reason}</li>)}
                </ul>
              </div>
            )}
            {leetcodeGaps.length > 0 && (
              <div className="insights__sublist">
                <span className="insights__sublist-title">Evidenced on LeetCode</span>
                <ul className="insights__list">
                  {leetcodeGaps.map((g, i) => <li key={i}><strong>{g.skill}</strong> — {g.reason}</li>)}
                </ul>
              </div>
            )}
            {certificateGaps.length > 0 && (
              <div className="insights__sublist">
                <span className="insights__sublist-title">Evidenced by certificates</span>
                <ul className="insights__list">
                  {certificateGaps.map((g, i) => <li key={i}><strong>{g.skill}</strong> — {g.reason}</li>)}
                </ul>
              </div>
            )}
            {projectSuggestions.length > 0 && (
              <div className="insights__sublist">
                <span className="insights__sublist-title">Project additions to consider</span>
                <ul className="insights__list">
                  {projectSuggestions.map((s, i) => <li key={i}>{s.reason}</li>)}
                </ul>
              </div>
            )}
            {timelineNotes.length > 0 && (
              <div className="insights__sublist">
                <span className="insights__sublist-title">Timeline plausibility notes</span>
                <ul className="insights__list">
                  {timelineNotes.map((n, i) => <li key={i}>{n.detail}</li>)}
                </ul>
              </div>
            )}
          </InsightRow>
        )}

        {claimRiskDetails.length > 0 && (
          <InsightRow
            title="Claim Consistency"
            summary={`${claimRiskDetails.length} unresolved finding(s)`}
            tone="warn"
          >
            <ul className="insights__list">
              {claimRiskDetails.map((c, i) => (
                <li key={i}>
                  <span className={`insights__risk insights__risk--${c.risk_level}`}>{c.risk_level}</span>
                  <strong>{c.project}</strong>: {c.headline}
                  {c.unsupported_claims?.length > 0 && (
                    <span className="insights__muted"> ({c.unsupported_claims.join(', ')})</span>
                  )}
                </li>
              ))}
            </ul>
          </InsightRow>
        )}

        {Object.keys(sourceFreshness).length > 0 && (
          <InsightRow
            title="Source Freshness"
            summary={needsAttention.length === 0 ? 'All sources synced' : `${needsAttention.length} source(s) need attention`}
            tone={needsAttention.length === 0 ? 'strong' : 'gap'}
          >
            {needsAttention.length === 0 ? (
              <p className="insights__muted">Every connected source is within its expected freshness window.</p>
            ) : (
              <ul className="insights__list">
                {needsAttention.map(([key, info]) => (
                  <li key={key}>
                    <strong>{SOURCE_LABELS[key] || key}</strong> —{' '}
                    {!info.connected ? 'never connected' : `${info.age_days} days old, past its freshness window`}
                  </li>
                ))}
              </ul>
            )}
          </InsightRow>
        )}

        {topSkills.length > 0 && (
          <InsightRow title="Why Polaris thinks this" summary={`${topSkills.length} evidenced skill(s)`} tone="neutral">
            <ul className="insights__list insights__list--evidence">
              {topSkills.slice(0, 10).map((s) => (
                <li key={s.skill}>
                  <strong>{s.skill}</strong> — {Math.round((s.confidence || 0) * 100)}% confidence
                  {s.corroboration_count ? `, ${s.corroboration_count} corroborating source(s)` : ''}
                  {s.sources?.length > 0 && (
                    <span className="insights__muted">
                      {' '}({s.sources.slice(0, 3).join(', ')}{s.sources.length > 3 ? `, +${s.sources.length - 3} more` : ''})
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </InsightRow>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default IdentityInsights