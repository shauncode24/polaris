import CollapsibleSection from '../common/CollapsibleSection'
import './WeeklyBriefCard.css'

function formatDelta(n, unit = '') {
  if (n == null) return null
  const sign = n > 0 ? '+' : ''
  return `${sign}${n}${unit}`
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
            {facts.leetcode_solved_delta != null && (
              <span className="weekly-brief__delta-chip">LeetCode {formatDelta(facts.leetcode_solved_delta)}</span>
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default WeeklyBriefCard