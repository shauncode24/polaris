import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import ResumeHealth from './ResumeHealth'
import './ResumeAnalysisPanel.css'

const CATEGORIES = [
  { key: 'parsing', label: 'Parsing & ATS Compatibility', weight: 25 },
  { key: 'completeness', label: 'Resume Completeness', weight: 20 },
  { key: 'content_quality', label: 'Content Quality', weight: 25 },
  { key: 'structure', label: 'Resume Structure & Organization', weight: 15 },
  { key: 'keywords', label: 'Keyword Coverage', weight: 10 },
  { key: 'professionalism', label: 'Professionalism', weight: 5 },
]

export default function ResumeAnalysisPanel({ analysis, onRunAnalysis, analysisLoading }) {
  const [showKeywordDetail, setShowKeywordDetail] = useState(false)

  if (!analysis) {
    return (
      <div className="rap">
        <div className="rap__header">
          <span className="rap__title">ATS Analysis</span>
        </div>
        <div className="rap__body" style={{ alignItems: 'center', textAlign: 'center', padding: '32px 20px' }}>
          <p style={{ fontSize: 13, color: 'var(--text-soft)', maxWidth: 320, marginBottom: 16 }}>
            Run the analysis engine to check parsing quality, structure, formatting, and keyword coverage.
          </p>
          <button className="rh__btn rh__btn--primary" onClick={() => onRunAnalysis()} disabled={analysisLoading}>
            {analysisLoading ? 'Analyzing…' : 'Run Analysis Engine'}
          </button>
        </div>
      </div>
    )
  }

  const { module_scores, modules = {}, warnings = [], created_at } = analysis
  const { keywords = {} } = modules

  const highIssues = warnings.filter(w => w.severity === 'high').length
  const otherIssues = warnings.length - highIssues

  return (
    <CollapsibleSection
      title="ATS Analysis"
      subtitle={`${analysis.overall_score}/100 · ${highIssues} high-priority · ${otherIssues} other issue${otherIssues !== 1 ? 's' : ''}`}
      defaultOpen={false}
      className="rap-collapsible"
    >
      <div className="rap__body">
        <div className="rap__modules">
          {CATEGORIES.map(({ key, label, weight }) => {
            const val = module_scores?.[key] ?? 0
            const tone = val >= 80 ? 'high' : val >= 50 ? 'mid' : 'low'
            return (
              <div className="rap__module-bar" key={key}>
                <div className="rap__module-meta">
                  <span className="rap__module-name">{label} <span style={{ fontSize: 10.5, color: 'var(--text-soft)', fontWeight: 500 }}>({weight}%)</span></span>
                  <span className="rap__module-score">{val}/100</span>
                </div>
                <div className="rap__bar-track">
                  <div className={`rap__bar-fill ${tone}`} style={{ width: `${val}%` }} />
                </div>
              </div>
            )
          })}
        </div>

        <div className="rap__keywords-section">
          <span className="rap__section-title">Keyword Coverage</span>
          <div className="rap__kw-summary">
            <span className="rap__kw-count rap__kw-count--match">{keywords.matched_count ?? 0} Matched</span>
            <span className="rap__kw-count rap__kw-count--missing">{keywords.missing_count ?? 0} Missing</span>
            <button type="button" className="rap__kw-toggle" onClick={() => setShowKeywordDetail(v => !v)}>
              {showKeywordDetail ? 'Hide details' : 'View details'}
            </button>
          </div>
          {showKeywordDetail && (
            <div className="rap__keyword-grid">
              {keywords.matched?.map((kw) => (
                <span className="rap__kw-badge rap__kw-badge--match" key={kw}>✓ {kw}</span>
              ))}
              {keywords.missing?.map((kw) => (
                <span className="rap__kw-badge rap__kw-badge--missing" key={kw}>+ {kw}</span>
              ))}
            </div>
          )}
        </div>

        <div>
          <span className="rap__section-title">ATS Warnings</span>
          <ResumeHealth ats_flags={warnings} />
        </div>
      </div>
    </CollapsibleSection>
  )
}