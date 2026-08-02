// frontend/src/components/identity/CoverageTimelinePanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './CoverageTimelinePanel.css'

function GapList({ title, items, reasonKey = 'reason', labelKey = 'skill' }) {
  if (!items || items.length === 0) return null
  return (
    <div className="coverage-panel__section">
      <span className="coverage-panel__section-title">{title}</span>
      <ul className="coverage-panel__list">
        {items.map((item, i) => (
          <li key={i}>
            <strong>{item[labelKey]}</strong> — {item[reasonKey]}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Surfaces facts.coverage_gaps (github_gaps, leetcode_gaps,
// certificate_gaps, project_suggestions) and
// facts.timeline_plausibility_notes — all computed deterministically
// but previously never rendered on the Identity page.
function CoverageTimelinePanel({ coverageGaps, timelineNotes = [] }) {
  const gh = coverageGaps?.github_gaps || []
  const lc = coverageGaps?.leetcode_gaps || []
  const cert = coverageGaps?.certificate_gaps || []
  const suggestions = coverageGaps?.project_suggestions || []

  const hasAny = gh.length || lc.length || cert.length || suggestions.length || timelineNotes.length
  if (!hasAny) return null

  return (
    <CollapsibleSection title="Coverage Gaps & Timeline Notes" defaultOpen={false}>
      <div className="coverage-panel">
        <GapList title="Evidenced on GitHub, missing from resume" items={gh} />
        <GapList title="Evidenced on LeetCode, missing from resume" items={lc} />
        <GapList title="Evidenced by certificates, missing from resume" items={cert} />

        {suggestions.length > 0 && (
          <div className="coverage-panel__section">
            <span className="coverage-panel__section-title">Project additions to consider</span>
            <ul className="coverage-panel__list">
              {suggestions.map((s, i) => (
                <li key={i}>{s.reason}</li>
              ))}
            </ul>
          </div>
        )}

        {timelineNotes.length > 0 && (
          <div className="coverage-panel__section">
            <span className="coverage-panel__section-title">Timeline plausibility notes</span>
            <ul className="coverage-panel__list">
              {timelineNotes.map((n, i) => (
                <li key={i}>{n.detail}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default CoverageTimelinePanel