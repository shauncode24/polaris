import './PortfolioDepthMaturity.css'

export default function ArchitectureMaturityCard({ insights }) {
  const architecture = insights?.architecture_maturity || {}
  const hasArchData = architecture.maturity_score !== undefined && architecture.maturity_score !== null

  const maturityScore = architecture.maturity_score ?? 0
  const radius = 45
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (maturityScore / 100) * circumference

  const labelMapping = {
    well_architected: 'Well Architected',
    layered: 'Layered Architecture',
    basic_structure: 'Basic Structure',
    flat_script: 'Flat / Script Style',
  }

  return (
    <div className="gh-depth__card">
      <h3 className="gh-depth__title">Architecture Maturity</h3>
      {hasArchData ? (
        <div className="gh-depth__arch-body">
          <div className="gh-depth__radial-container">
            <svg className="gh-depth__radial" width="120" height="120">
              <circle className="gh-depth__radial-bg" cx="60" cy="60" r={radius} strokeWidth="10" />
              <circle
                className="gh-depth__radial-fill"
                cx="60" cy="60" r={radius} strokeWidth="10"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
              />
            </svg>
            <div className="gh-depth__radial-label">
              <span className="gh-depth__radial-score">{maturityScore}</span>
              <span className="gh-depth__radial-max">/100</span>
            </div>
          </div>

          <div className="gh-depth__arch-info">
            <div className="gh-depth__maturity-label">{architecture.maturity_label}</div>
            <div className="gh-depth__maturity-count">
              Assessed {architecture.assessed_repos} of {architecture.total_repos_considered} eligible repos
            </div>
          </div>

          <div className="gh-depth__dist">
            {Object.entries(architecture.distribution_pct || {}).map(([key, pct]) => (
              <div className="gh-depth__dist-row" key={key}>
                <span className="gh-depth__dist-label">{labelMapping[key] || key}</span>
                <div className="gh-depth__dist-bar-wrap">
                  <div className="gh-depth__dist-bar-track">
                    <div className="gh-depth__dist-bar-fill" style={{ width: `${pct}%` }} />
                  </div>
                </div>
                <span className="gh-depth__dist-pct">{pct}%</span>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="gh-depth__empty">
          Not enough architectural data available. Assess repository structure to see maturity rollup.
        </div>
      )}
    </div>
  )
}