// frontend/src/components/identity/ClaimFreshnessPanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './ClaimFreshnessPanel.css'

const SOURCE_LABELS = {
  resume: 'Resume',
  github: 'GitHub',
  leetcode: 'LeetCode',
  claim_audit: 'Claim Audit',
  job_descriptions: 'Job Descriptions',
}

// Surfaces facts.claim_risk_details (structured list — previously only
// echoed indirectly through the LLM's free-text "contradictions"),
// facts.evidence_coverage, and facts.source_freshness (per-source
// as_of/age_days/is_stale/connected — computed by freshness.py but
// never rendered; only the LLM's prose "freshness_note" summary of it
// was ever shown, never the underlying structured data).
function ClaimFreshnessPanel({ claimRiskDetails = [], sourceFreshness = {}, evidenceCoverage }) {
  const sources = Object.entries(sourceFreshness)
  const hasAny = claimRiskDetails.length > 0 || sources.length > 0 || evidenceCoverage

  if (!hasAny) return null

  return (
    <CollapsibleSection title="Claim Risk & Evidence Freshness" defaultOpen={false}>
      <div className="claim-fresh">
        {claimRiskDetails.length > 0 && (
          <div className="claim-fresh__section">
            <span className="claim-fresh__section-title">Unresolved Claim Risk</span>
            <ul className="claim-fresh__list">
              {claimRiskDetails.map((c, i) => (
                <li key={i}>
                  <span className={`claim-fresh__risk claim-fresh__risk--${c.risk_level}`}>{c.risk_level}</span>
                  <strong>{c.project}</strong>: {c.headline}
                  {c.unsupported_claims?.length > 0 && (
                    <span className="claim-fresh__claims"> ({c.unsupported_claims.join(', ')})</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {evidenceCoverage && (
          <div className="claim-fresh__section">
            <span className="claim-fresh__section-title">Evidence Coverage</span>
            <p className="claim-fresh__coverage">
              {evidenceCoverage.completeness_label} — {evidenceCoverage.connected_sources}/{evidenceCoverage.total_sources} connected,
              {' '}{evidenceCoverage.stale_sources} stale, {evidenceCoverage.missing_sources} missing
              {' '}(score {Math.round((evidenceCoverage.completeness_score || 0) * 100)}%).
            </p>
          </div>
        )}

        {sources.length > 0 && (
          <div className="claim-fresh__section">
            <span className="claim-fresh__section-title">Source Freshness</span>
            <div className="claim-fresh__sources">
              {sources.map(([key, info]) => (
                <div className="claim-fresh__source-row" key={key}>
                  <span className="claim-fresh__source-name">{SOURCE_LABELS[key] || key}</span>
                  <span
                    className={`claim-fresh__source-badge ${
                      !info.connected
                        ? 'claim-fresh__source-badge--missing'
                        : info.is_stale
                        ? 'claim-fresh__source-badge--stale'
                        : 'claim-fresh__source-badge--fresh'
                    }`}
                  >
                    {!info.connected ? 'Never connected' : info.is_stale ? `Stale (${info.age_days}d)` : `Fresh (${info.age_days}d)`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default ClaimFreshnessPanel