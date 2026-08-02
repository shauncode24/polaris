import CollapsibleSection from '../common/CollapsibleSection'
import './ExecutiveSummary.css'

export default function ExecutiveSummary({ analysis, review }) {
  if (!analysis && !review) return null

  const summaryText =
    review?.summary ||
    (analysis
      ? `Your resume currently scores ${analysis.overall_score}/100 (${analysis.label}). Run AI Review for a personalized narrative summary.`
      : null)

  const strengths = (review?.strengths?.length ? review.strengths : []).slice(0, 3)
  const weaknesses = (
    review?.top_priority_fixes?.length ? review.top_priority_fixes : (analysis?.suggestions || []).filter(s => s.priority === 'high').map(s => s.title)
  ).slice(0, 3)

  const opportunity = analysis?.suggestions?.[0]

  if (!summaryText && strengths.length === 0 && weaknesses.length === 0 && !opportunity) return null

  return (
    <CollapsibleSection title="Executive Summary" defaultOpen={true} className="exsum" dense>
      <div className="exsum__body">
        {summaryText && <p className="exsum__text">{summaryText}</p>}

        {opportunity && (
          <div className="exsum__opportunity">
            <span className="exsum__opportunity-label">Biggest opportunity</span>
            <span className="exsum__opportunity-text">{opportunity.title}</span>
          </div>
        )}

        {(strengths.length > 0 || weaknesses.length > 0) && (
          <div className="exsum__grid">
            {strengths.length > 0 && (
              <div className="exsum__col">
                <div className="exsum__col-title exsum__col-title--good">Strengths</div>
                {strengths.map((s, i) => (
                  <div className="exsum__row exsum__row--good" key={i}>
                    <span>✓</span>{s}
                  </div>
                ))}
              </div>
            )}
            {weaknesses.length > 0 && (
              <div className="exsum__col">
                <div className="exsum__col-title exsum__col-title--bad">Weaknesses</div>
                {weaknesses.map((s, i) => (
                  <div className="exsum__row exsum__row--bad" key={i}>
                    <span>✗</span>{s}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {!review && (
          <div className="exsum__cta-hint">Run AI Review to get personalized strengths &amp; weaknesses.</div>
        )}
      </div>
    </CollapsibleSection>
  )
}