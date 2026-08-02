import React from 'react'
import './PortfolioSignals.css'

function getTrendDetails(trend) {
  if (!trend) return { label: 'No data', className: 'trend-neutral', icon: '•' }
  const lower = trend.toLowerCase()
  if (lower.includes('improving') || lower.includes('increasing')) {
    return { label: trend, className: 'trend-up', icon: '↑' }
  }
  if (lower.includes('declining') || lower.includes('decreasing')) {
    return { label: trend, className: 'trend-down', icon: '↓' }
  }
  return { label: trend, className: 'trend-neutral', icon: '→' }
}

export default function PortfolioSignals({ insights }) {
  if (!insights) return null

  const profile = insights.portfolio_profile || {}
  const practices = insights.engineering_practices || {}
  const progress = insights.progress || {}
  const strengths = insights.strengths || []

  const domains = profile.domains || []
  const projectTypes = profile.project_types || []

  // Aggregate values
  const avgHygiene = practices.commit_hygiene?.average_score
  const collaborativeCount = practices.collaboration?.collaborative_or_mixed_repos

  // Trends
  const backendTrend = getTrendDetails(progress.backend_activity)
  const docTrend = getTrendDetails(progress.documentation)
  const testTrend = getTrendDetails(progress.testing)
  const recentFocus = progress.recent_focus
  const newTech = progress.new_technologies || []

  return (
    <div className="gh-signals">
      <div className="gh-signals__grid">
        {/* Card 1: Portfolio Profile */}
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

        {/* Card 2: Key Strengths */}
        <div className="gh-signals__card">
          <h3 className="gh-signals__title">Key Strengths</h3>
          {strengths.length > 0 ? (
            <ul className="gh-signals__strengths-list">
              {strengths.map((str, idx) => (
                <li key={idx} className="gh-signals__strength-item">
                  <span className="gh-signals__strength-icon">✓</span>
                  <span className="gh-signals__strength-text">{str}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="gh-signals__fallback">No deterministic strengths identified yet.</p>
          )}
        </div>

        {/* Card 3: Progress & Trends */}
        <div className="gh-signals__card">
          <h3 className="gh-signals__title">Progress & Focus</h3>
          <div className="gh-signals__trends-grid">
            <div className="gh-signals__trend-row">
              <span className="gh-signals__trend-label">Backend Activity</span>
              <span className={`gh-signals__trend-badge ${backendTrend.className}`}>
                <span className="gh-signals__trend-icon">{backendTrend.icon}</span> {backendTrend.label}
              </span>
            </div>
            <div className="gh-signals__trend-row">
              <span className="gh-signals__trend-label">Documentation Trend</span>
              <span className={`gh-signals__trend-badge ${docTrend.className}`}>
                <span className="gh-signals__trend-icon">{docTrend.icon}</span> {docTrend.label}
              </span>
            </div>
            <div className="gh-signals__trend-row">
              <span className="gh-signals__trend-label">Testing Trend</span>
              <span className={`gh-signals__trend-badge ${testTrend.className}`}>
                <span className="gh-signals__trend-icon">{testTrend.icon}</span> {testTrend.label}
              </span>
            </div>
          </div>

          <div className="gh-signals__focus-section">
            <div className="gh-signals__focus-row">
              <span className="gh-signals__trend-label">Recent Focus:</span>
              <span className="gh-signals__focus-value">{recentFocus || 'None'}</span>
            </div>
            {newTech.length > 0 && (
              <div className="gh-signals__focus-row">
                <span className="gh-signals__trend-label">New Tech Added:</span>
                <div className="gh-signals__chips gh-signals__chips--sm">
                  {newTech.map((tech) => (
                    <span key={tech} className="gh-signals__chip gh-signals__chip--new-tech">{tech}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Card 4: Aggregate Practices */}
        <div className="gh-signals__card">
          <h3 className="gh-signals__title">Aggregate Practices</h3>
          <div className="gh-signals__practices">
            <div className="gh-signals__practice-item">
              <div className="gh-signals__practice-header">
                <span className="gh-signals__practice-title">Avg Commit message hygiene</span>
                <span className="gh-signals__practice-value">
                  {avgHygiene !== null && avgHygiene !== undefined ? `${avgHygiene}/100` : '—'}
                </span>
              </div>
              {avgHygiene !== null && avgHygiene !== undefined && (
                <div className="gh-signals__bar-track">
                  <div className="gh-signals__bar-fill" style={{ width: `${avgHygiene}%` }} />
                </div>
              )}
            </div>

            <div className="gh-signals__practice-item" style={{ marginTop: '16px' }}>
              <span className="gh-signals__practice-title" style={{ display: 'block', marginBottom: '8px' }}>Collaboration Density</span>
              <div className="gh-signals__collab-stat">
                <span className="gh-signals__collab-count">{collaborativeCount ?? 0}</span>
                <span className="gh-signals__collab-label">
                  repositor{collaborativeCount === 1 ? 'y' : 'ies'} with collaborative or mixed commits
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
