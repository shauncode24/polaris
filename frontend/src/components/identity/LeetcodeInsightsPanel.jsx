// frontend/src/components/identity/LeetcodeInsightsPanel.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './LeetcodeInsightsPanel.css'

// Surfaces facts.engineering_quadrant, facts.company_readiness, and
// facts.leetcode_topic_mastery — three fully-computed backend objects
// that previously had no representation anywhere in the Identity UI
// (the LeetCode page shows some of this independently, but the
// Identity module's own reconciled copy of these facts was invisible).
function LeetcodeInsightsPanel({ quadrant, companyReadiness = [], topicMastery = [] }) {
  const hasAny = quadrant || companyReadiness.length > 0 || topicMastery.length > 0
  if (!hasAny) return null

  const practicedTopics = topicMastery.filter((t) => t.problems > 0)

  return (
    <CollapsibleSection title="LeetCode & Engineering Quadrant" defaultOpen={false}>
      <div className="lc-insights">
        {quadrant && (
          <div className="lc-insights__quadrant">
            <span className="lc-insights__quadrant-label">{quadrant.quadrant_label}</span>
            <p className="lc-insights__quadrant-desc">{quadrant.description}</p>
            <div className="lc-insights__quadrant-scores">
              <span>LeetCode {quadrant.leetcode_score}/100</span>
              <span>GitHub {quadrant.github_score}/100</span>
            </div>
          </div>
        )}

        {companyReadiness.length > 0 && (
          <div className="lc-insights__section">
            <span className="lc-insights__section-title">Company Readiness</span>
            <div className="lc-insights__company-list">
              {companyReadiness.map((c) => (
                <div className="lc-insights__company-row" key={c.company}>
                  <span className="lc-insights__company-name">{c.company}</span>
                  <div className="lc-insights__company-track">
                    <div className="lc-insights__company-fill" style={{ width: `${c.readiness_pct}%` }} />
                  </div>
                  <span className="lc-insights__company-pct">{c.readiness_pct}%</span>
                  {c.weak_topics?.length > 0 && (
                    <span className="lc-insights__company-weak">Weak: {c.weak_topics.join(', ')}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {practicedTopics.length > 0 && (
          <div className="lc-insights__section">
            <span className="lc-insights__section-title">Topic Mastery</span>
            <div className="lc-insights__topics">
              {practicedTopics.map((t) => (
                <span className="lc-insights__topic-chip" key={t.topic}>
                  {t.topic}: {t.mastery} ({t.problems})
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default LeetcodeInsightsPanel