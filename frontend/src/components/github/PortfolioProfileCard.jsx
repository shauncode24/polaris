import './PortfolioSignals.css'

export default function PortfolioProfileCard({ insights }) {
  const profile = insights?.portfolio_profile || {}
  const domains = profile.domains || []
  const projectTypes = profile.project_types || []

  return (
    <div className="gh-signals__card">
      <h3 className="gh-signals__title">Portfolio Profile</h3>
      <div className="gh-signals__section">
        <span className="gh-signals__section-title">Assessed Domains</span>
        {domains.length > 0 ? (
          <div className="gh-signals__chips">
            {domains.map((dom) => (
              <span key={dom} className="gh-signals__chip gh-signals__chip--domain">{dom}</span>
            ))}
          </div>
        ) : (
          <p className="gh-signals__fallback">No domains detected.</p>
        )}
      </div>
      <div className="gh-signals__section">
        <span className="gh-signals__section-title">Project Types</span>
        {projectTypes.length > 0 ? (
          <div className="gh-signals__chips">
            {projectTypes.map((type) => (
              <span key={type} className="gh-signals__chip gh-signals__chip--type">{type}</span>
            ))}
          </div>
        ) : (
          <p className="gh-signals__fallback">No project types detected.</p>
        )}
      </div>
    </div>
  )
}