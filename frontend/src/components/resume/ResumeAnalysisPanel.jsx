import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeAnalysisPanel.css'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

const CATEGORIES = [
  { key: 'parsing', label: 'Parsing & ATS Compatibility', weight: 25 },
  { key: 'completeness', label: 'Resume Completeness', weight: 20 },
  { key: 'content_quality', label: 'Content Quality', weight: 25 },
  { key: 'structure', label: 'Resume Structure & Organization', weight: 15 },
  { key: 'keywords', label: 'Keyword Coverage', weight: 10 },
  { key: 'professionalism', label: 'Professionalism', weight: 5 },
]

export default function ResumeAnalysisPanel({ analysis, onRunAnalysis, analysisLoading }) {
  if (!analysis) {
    return (
      <div className="rap">
        <div className="rap__header">
          <span className="rap__title">Resume Analysis</span>
        </div>
        <div className="rap__body" style={{ alignItems: 'center', textAlign: 'center', padding: '40px 20px' }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--border)', marginBottom: 12 }}>
            <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" />
          </svg>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', marginBottom: 6 }}>Resume Analysis Pending</h3>
          <p style={{ fontSize: 13, color: 'var(--text-soft)', maxWidth: 280, marginBottom: 16 }}>
            Run the analysis engine to inspect parsing quality, structure, content bullets, formatting, and profile evidence.
          </p>
          <button
            className="rh__btn rh__btn--primary"
            onClick={onRunAnalysis}
            disabled={analysisLoading}
          >
            {analysisLoading ? 'Analyzing…' : 'Run Analysis Engine'}
          </button>
        </div>
      </div>
    )
  }

  const { overall_score: score, grade, label, module_scores, modules = {}, suggestions = [], created_at } = analysis

  // Extract module reports
  const { keywords = {}, evidence = {} } = modules

  return (
    <div className="rap-container">
      <div className="rap__header-summary">
        <h3 className="rap__title-main">Analysis Report</h3>
        {created_at && <span className="rap__date">Calculated {formatDate(created_at)}</span>}
      </div>

      <div className="rap__collapsible-stack">
        {/* Score Radial & Modules grid */}
        <CollapsibleSection title="Analysis Score & Modules" defaultOpen={true}>
          <div className="rap__score-section">
            <div className="rap__radial-wrap">
              <div className="rap__radial" style={{ '--score': score }}>
                <div className="rap__radial-content">
                  <span className="rap__grade">{grade}</span>
                  <span className="rap__raw-score">{score}/100</span>
                </div>
              </div>
              <span className="rap__score-label">{label}</span>
            </div>

            <div className="rap__modules">
              {CATEGORIES.map(({ key, label, weight }) => {
                const val = module_scores?.[key] ?? 0
                const tone = val >= 80 ? 'high' : val >= 50 ? 'mid' : 'low'
                return (
                  <div className="rap__module-bar" key={key}>
                    <div className="rap__module-meta">
                      <div className="rap__module-name-group" style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span className="rap__module-name">{label}</span>
                        <span className="rap__module-weight" style={{ fontSize: '10.5px', color: 'var(--text-soft)', fontWeight: 500 }}>({weight}%)</span>
                      </div>
                      <span className="rap__module-score">{val}/100</span>
                    </div>
                    <div className="rap__bar-track">
                      <div className={`rap__bar-fill ${tone}`} style={{ width: `${val}%` }} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </CollapsibleSection>

        {/* Suggestion action cards */}
        {suggestions.length > 0 && (
          <CollapsibleSection title="Prioritized Action Items" defaultOpen={true}>
            <div className="rap__suggestions-section">
              <div className="rap__sug-list">
                {suggestions.map((sug, i) => (
                  <div className="rap__sug-card" key={i}>
                    <div className={`rap__sug-indicator ${sug.priority}`} />
                    <div className="rap__sug-content">
                      <div className="rap__sug-header-row">
                        <span className="rap__sug-title">{sug.title}</span>
                        <span className={`rap__sug-badge ${sug.priority}`}>{sug.priority}</span>
                      </div>
                      <p className="rap__sug-desc">{sug.detail}</p>
                      {sug.impact && <span className="rap__sug-impact">{sug.impact}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </CollapsibleSection>
        )}

        {/* Keywords matched vs missing */}
        {keywords.matched && (
          <CollapsibleSection title="Keyword Coverage" defaultOpen={false}>
            <div className="rap__keywords-section">
              <div className="rap__keyword-grid">
                {keywords.matched.map((kw) => (
                  <span className="rap__kw-badge rap__kw-badge--match" key={kw}>
                    ✓ {kw} <em>{keywords.using_default ? 'Found' : 'Required · Found'}</em>
                  </span>
                ))}
                {keywords.missing?.map((kw) => (
                  <span className="rap__kw-badge rap__kw-badge--missing" key={kw}>
                    + {kw} <em>{keywords.using_default ? 'Suggested' : 'Required · Missing'}</em>
                  </span>
                ))}
              </div>
            </div>
          </CollapsibleSection>
        )}

        {/* Evidence matrix */}
        {evidence.skills && evidence.skills.length > 0 && (
          <CollapsibleSection title="Skill Evidence Matrix" defaultOpen={false}>
            <div className="rap__evidence-section">
              <div className="rap__table-wrap">
                <table className="rap__table">
                  <thead>
                    <tr>
                      <th>Skill</th>
                      <th style={{ textAlign: 'center' }}>Experience</th>
                      <th style={{ textAlign: 'center' }}>Project</th>
                      <th style={{ textAlign: 'center' }}>GitHub</th>
                      <th style={{ textAlign: 'center' }}>Leetcode</th>
                      <th style={{ textAlign: 'center' }}>Certs</th>
                      <th style={{ textAlign: 'right' }}>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evidence.skills.map((skill) => (
                      <tr key={skill.canonical}>
                        <td style={{ fontWeight: 600, color: 'var(--ink)' }}>{skill.name}</td>
                        <td style={{ textAlign: 'center' }}>
                          {skill.in_experience ? <span className="rap__check-icon">✓</span> : <span className="rap__cross-icon">✕</span>}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {skill.in_project ? <span className="rap__check-icon">✓</span> : <span className="rap__cross-icon">✕</span>}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {skill.in_github ? <span className="rap__check-icon">✓</span> : <span className="rap__cross-icon">✕</span>}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {skill.in_leetcode ? <span className="rap__check-icon">✓</span> : <span className="rap__cross-icon">✕</span>}
                        </td>
                        <td style={{ textAlign: 'center' }}>
                          {skill.in_certificate ? <span className="rap__check-icon">✓</span> : <span className="rap__cross-icon">✕</span>}
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <span className={`rap__conf-badge ${skill.confidence}`}>
                            {skill.confidence}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </CollapsibleSection>
        )}
      </div>
    </div>
  )
}
