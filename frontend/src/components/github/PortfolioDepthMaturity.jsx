import { useState } from 'react'
import './PortfolioDepthMaturity.css'

export default function PortfolioDepthMaturity({ insights }) {
  const [expandedTech, setExpandedTech] = useState(null)

  const architecture = insights?.architecture_maturity || {}
  const techDepth = insights?.technology_depth || {}

  const hasArchData = architecture.maturity_score !== undefined && architecture.maturity_score !== null
  const techEntries = Object.entries(techDepth)
    .map(([name, data]) => ({ name, ...data }))
    .sort((a, b) => b.score - a.score)

  const maturityScore = architecture.maturity_score ?? 0
  const radius = 45
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (maturityScore / 100) * circumference

  function getDepthColorClass(label) {
    switch (label) {
      case 'Deep expertise': return 'gh-depth__badge--deep'
      case 'Working proficiency': return 'gh-depth__badge--working'
      case 'Applied exposure': return 'gh-depth__badge--applied'
      default: return 'gh-depth__badge--surface'
    }
  }

  const labelMapping = {
    well_architected: 'Well Architected',
    layered: 'Layered Architecture',
    basic_structure: 'Basic Structure',
    flat_script: 'Flat / Script Style'
  }

  return (
    <div className="gh-depth">
      <div className="gh-depth__grid">
        {/* Architecture Maturity Card */}
        <div className="gh-depth__card gh-depth__card--arch">
          <h3 className="gh-depth__title">Architecture Maturity</h3>
          {hasArchData ? (
            <div className="gh-depth__arch-body">
              <div className="gh-depth__radial-container">
                <svg className="gh-depth__radial" width="120" height="120">
                  <circle
                    className="gh-depth__radial-bg"
                    cx="60"
                    cy="60"
                    r={radius}
                    strokeWidth="10"
                  />
                  <circle
                    className="gh-depth__radial-fill"
                    cx="60"
                    cy="60"
                    r={radius}
                    strokeWidth="10"
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

        {/* Technology Depth Card */}
        <div className="gh-depth__card gh-depth__card--tech">
          <h3 className="gh-depth__title">Technology Depth & Proficiency</h3>
          {techEntries.length > 0 ? (
            <div className="gh-depth__tech-list">
              <p className="gh-depth__subtitle">
                Combines repo count, recency, code architecture depth, and commit hygiene. Click a row to see details.
              </p>
              {techEntries.map((tech) => {
                const isExpanded = expandedTech === tech.name
                return (
                  <div
                    key={tech.name}
                    className={`gh-depth__row ${isExpanded ? 'gh-depth__row--expanded' : ''}`}
                    onClick={() => setExpandedTech(isExpanded ? null : tech.name)}
                  >
                    <div className="gh-depth__row-header">
                      <div className="gh-depth__tech-info">
                        <span className="gh-depth__tech-name">{tech.name}</span>
                        <span className={`gh-depth__badge ${getDepthColorClass(tech.label)}`}>
                          {tech.label}
                        </span>
                      </div>
                      <div className="gh-depth__score-box">
                        <span className="gh-depth__score-val">{tech.score}</span>
                        <span className="gh-depth__score-lbl">/100</span>
                        <svg
                          className={`gh-depth__chevron ${isExpanded ? 'gh-depth__chevron--rotated' : ''}`}
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <polyline points="6 9 12 15 18 9" />
                        </svg>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="gh-depth__breakdown" onClick={(e) => e.stopPropagation()}>
                        <div className="gh-depth__breakdown-grid">
                          <div className="gh-depth__breakdown-item">
                            <span className="gh-depth__b-label">Breadth ({tech.repo_count} {tech.repo_count === 1 ? 'repo' : 'repos'})</span>
                            <div className="gh-depth__b-bar-track">
                              <div className="gh-depth__b-bar-fill" style={{ width: `${(tech.breakdown.breadth / 25) * 100}%` }} />
                            </div>
                            <span className="gh-depth__b-val">{tech.breakdown.breadth}/25</span>
                          </div>

                          <div className="gh-depth__breakdown-item">
                            <span className="gh-depth__b-label">Recency (active window)</span>
                            <div className="gh-depth__b-bar-track">
                              <div className="gh-depth__b-bar-fill" style={{ width: `${(tech.breakdown.recency / 25) * 100}%` }} />
                            </div>
                            <span className="gh-depth__b-val">{tech.breakdown.recency}/25</span>
                          </div>

                          <div className="gh-depth__breakdown-item">
                            <span className="gh-depth__b-label">Architecture Strength</span>
                            <div className="gh-depth__b-bar-track">
                              <div className="gh-depth__b-bar-fill" style={{ width: `${(tech.breakdown.architecture / 30) * 100}%` }} />
                            </div>
                            <span className="gh-depth__b-val">{tech.breakdown.architecture}/30</span>
                          </div>

                          <div className="gh-depth__breakdown-item">
                            <span className="gh-depth__b-label">Commit Hygiene</span>
                            <div className="gh-depth__b-bar-track">
                              <div className="gh-depth__b-bar-fill" style={{ width: `${(tech.breakdown.commit_hygiene / 20) * 100}%` }} />
                            </div>
                            <span className="gh-depth__b-val">{tech.breakdown.commit_hygiene}/20</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="gh-depth__empty">
              No technology evidence found. Sync public GitHub repositories to see tech depth profile.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
