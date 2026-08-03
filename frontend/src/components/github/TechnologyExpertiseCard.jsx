import { useState } from 'react'
import './PortfolioDepthMaturity.css'
import './TechnologyExpertiseCard.css'

function getDepthColorClass(label) {
  switch (label) {
    case 'Deep expertise': return 'gh-depth__badge--deep'
    case 'Working proficiency': return 'gh-depth__badge--working'
    case 'Applied exposure': return 'gh-depth__badge--applied'
    default: return 'gh-depth__badge--surface'
  }
}

export default function TechnologyExpertiseCard({ technologyDepth, skillConfidenceExplanations, languages }) {
  const [expandedTech, setExpandedTech] = useState(null)

  const explanationByTech = new Map(
    (skillConfidenceExplanations || []).map((sce) => [sce.skill.toLowerCase(), sce.explanation])
  )

  const techEntries = Object.entries(technologyDepth || {})
    .map(([name, data]) => ({ name, ...data, explanation: explanationByTech.get(name.toLowerCase()) }))
    .sort((a, b) => b.score - a.score)

  const totalBytes = (languages || []).reduce((sum, l) => sum + (l.bytes || 0), 0)
  const topLanguages = (languages || [])
    .map((l) => ({ ...l, pct: totalBytes > 0 ? Math.round((l.bytes / totalBytes) * 100) : 0 }))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 5)

  return (
    <div className="gh-depth__card gh-tech-card">
      <h3 className="gh-depth__title">Technology Expertise</h3>
      <p className="gh-depth__subtitle">
        Language breadth, then depth per technology — evidence, repositories, architecture, and confidence, all in one place.
      </p>

      {topLanguages.length > 0 && (
        <div className="gh-tech__langs">
          {topLanguages.map((l) => (
            <div key={l.language} className="gh-tech__lang-row">
              <span className="gh-tech__lang-name">{l.language}</span>
              <div className="gh-tech__lang-track">
                <div className="gh-tech__lang-fill" style={{ width: `${l.pct}%` }} />
              </div>
              <span className="gh-tech__lang-pct">{l.pct}%</span>
            </div>
          ))}
        </div>
      )}

      {techEntries.length > 0 ? (
        <div className="gh-depth__tech-list">
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
                    <span className={`gh-depth__badge ${getDepthColorClass(tech.label)}`}>{tech.label}</span>
                  </div>
                  <div className="gh-depth__score-box">
                    <span className="gh-depth__score-val">{tech.score}</span>
                    <span className="gh-depth__score-lbl">/100</span>
                    <svg
                      className={`gh-depth__chevron ${isExpanded ? 'gh-depth__chevron--rotated' : ''}`}
                      width="16" height="16" viewBox="0 0 24 24" fill="none"
                      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </div>

                {isExpanded && (
                  <div className="gh-depth__breakdown" onClick={(e) => e.stopPropagation()}>
                    {tech.explanation && (
                      <p className="gh-tech__explanation">{tech.explanation}</p>
                    )}
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
          No technology evidence found. Sync public GitHub repositories to see your expertise profile.
        </div>
      )}
    </div>
  )
}