// frontend/src/components/identity/GithubDeepDivePanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './GithubDeepDivePanel.css'

const TREND_TONE = { Improving: 'up', Declining: 'down', Unchanged: 'flat' }

function TrendChip({ label, value }) {
  if (!value) return null
  const tone = TREND_TONE[value] || 'flat'
  return (
    <span className={`gh-deep__trend gh-deep__trend--${tone}`}>
      {label}: {value}
    </span>
  )
}

// Surfaces facts.github_progress (recent_focus, backend_activity,
// documentation/testing trends, new_technologies) and the full
// facts.architecture_maturity object (previously only maturity_score/
// maturity_label were shown; assessed/unassessed counts and the
// depth-label distribution were computed but never displayed).
function GithubDeepDivePanel({ progress, architectureMaturity }) {
  const hasProgress = progress && Object.keys(progress).length > 0
  const hasMaturity = architectureMaturity && architectureMaturity.maturity_score != null
  const distribution = architectureMaturity?.distribution_pct || {}

  if (!hasProgress && !hasMaturity) return null

  return (
    <CollapsibleSection title="GitHub Progress & Architecture" defaultOpen={false}>
      <div className="gh-deep">
        {hasProgress && (
          <div className="gh-deep__section">
            <span className="gh-deep__section-title">Progress since last sync</span>
            {progress.recent_focus && <p className="gh-deep__line">Recent focus: {progress.recent_focus}</p>}
            <div className="gh-deep__trends">
              <TrendChip label="Backend activity" value={progress.backend_activity} />
              <TrendChip label="Documentation" value={progress.documentation} />
              <TrendChip label="Testing" value={progress.testing} />
            </div>
            {progress.new_technologies?.length > 0 && (
              <p className="gh-deep__line">New technologies: {progress.new_technologies.join(', ')}</p>
            )}
          </div>
        )}

        {hasMaturity && (
          <div className="gh-deep__section">
            <span className="gh-deep__section-title">Architecture Maturity</span>
            <div className="gh-deep__maturity">
              <span className="gh-deep__maturity-score">{architectureMaturity.maturity_score}/100</span>
              <span className="gh-deep__maturity-label">{architectureMaturity.maturity_label}</span>
            </div>
            <p className="gh-deep__line">
              {architectureMaturity.assessed_repos} of {architectureMaturity.total_repos_considered} eligible repos assessed
              {architectureMaturity.unassessed_repos ? ` (${architectureMaturity.unassessed_repos} unassessed)` : ''}.
            </p>
            {Object.keys(distribution).length > 0 && (
              <div className="gh-deep__dist">
                {Object.entries(distribution).map(([label, pct]) => (
                  <span key={label} className="gh-deep__dist-chip">{label.replace(/_/g, ' ')}: {pct}%</span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default GithubDeepDivePanel