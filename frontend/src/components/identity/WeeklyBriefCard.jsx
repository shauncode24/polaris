// frontend/src/components/identity/WeeklyBriefCard.jsx
import CollapsibleSection from '../common/CollapsibleSection'
import './WeeklyBriefCard.css'

function formatDelta(n, unit = '') {
  if (n == null) return null
  const sign = n > 0 ? '+' : ''
  return `${sign}${n}${unit}`
}

function SkillDeltaList({ title, items, tone }) {
  if (!items || items.length === 0) return null
  return (
    <div className="weekly-brief__skill-deltas">
      <span className="weekly-brief__skill-deltas-title">{title}</span>
      <div className="weekly-brief__skill-chips">
        {items.map((s) => (
          <span key={s.skill} className={`weekly-brief__skill-chip weekly-brief__skill-chip--${tone}`}>
            {s.skill} {s.delta > 0 ? '+' : ''}{Math.round(s.delta * 100)}%
          </span>
        ))}
      </div>
    </div>
  )
}

function WeeklyBriefCard({ brief, onRefresh, loading, error }) {
  const narrative = brief?.narrative
  const facts = brief?.facts

  return (
    <CollapsibleSection title="Weekly Brief" defaultOpen={true} className="weekly-brief">
      <div className="weekly-brief__body">
        <div className="weekly-brief__header-row">
          {narrative?.headline && <span className="weekly-brief__headline">{narrative.headline}</span>}
          <button type="button" className="weekly-brief__refresh" onClick={onRefresh} disabled={loading}>
            {loading ? '…' : '↻ Refresh'}
          </button>
        </div>

        {error && <p className="weekly-brief__error">{error}</p>}

        {!brief && !loading && !error && (
          <p className="identity-empty-text">No weekly brief yet — click refresh to generate one.</p>
        )}

        {facts && !facts.previous_generated_at && (
          <p className="identity-empty-text">
            First snapshot recorded — check back once a second one exists to compare against.
          </p>
        )}

        {narrative?.whats_changed?.length > 0 && (
          <ul className="weekly-brief__list">
            {narrative.whats_changed.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        )}

        {narrative?.biggest_leverage_move && (
          <div className="weekly-brief__leverage">
            <span className="weekly-brief__leverage-label">Biggest leverage move</span>
            <p>{narrative.biggest_leverage_move}</p>
          </div>
        )}

        {facts && (
          <div className="weekly-brief__deltas">
            {facts.resume_score_delta != null && (
              <span className="weekly-brief__delta-chip">Resume {formatDelta(facts.resume_score_delta)}</span>
            )}
            {facts.github_commits_delta != null && (
              <span className="weekly-brief__delta-chip">Commits {formatDelta(facts.github_commits_delta)}</span>
            )}
            {facts.github_new_repos > 0 && (
              <span className="weekly-brief__delta-chip">+{facts.github_new_repos} new repo(s)</span>
            )}
            {facts.github_documentation_trend && (
              <span className="weekly-brief__delta-chip">Docs: {facts.github_documentation_trend}</span>
            )}
            {facts.github_testing_trend && (
              <span className="weekly-brief__delta-chip">Testing: {facts.github_testing_trend}</span>
            )}
            {facts.leetcode_solved_delta != null && (
              <span className="weekly-brief__delta-chip">LeetCode {formatDelta(facts.leetcode_solved_delta)}</span>
            )}
          </div>
        )}

        {facts?.github_new_technologies?.length > 0 && (
          <p className="weekly-brief__new-tech">
            New GitHub technologies: {facts.github_new_technologies.join(', ')}
          </p>
        )}

        <SkillDeltaList title="Skills strengthened" items={facts?.skills_strengthened} tone="up" />
        <SkillDeltaList title="Skills weakened" items={facts?.skills_weakened} tone="down" />

        {facts?.goals_progress?.length > 0 && (
          <div className="weekly-brief__goals">
            <span className="weekly-brief__goals-title">Goal progress</span>
            {facts.goals_progress.map((g, i) => (
              <div key={i} className="weekly-brief__goal-row">
                <span>{g.title}</span>
                <span>{g.status_pct}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default WeeklyBriefCard