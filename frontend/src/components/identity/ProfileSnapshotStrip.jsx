// frontend/src/components/identity/ProfileSnapshotStrip.jsx
import Card from '../common/Card'
import './ProfileSnapshotStrip.css'

function Stat({ label, value }) {
  if (value === null || value === undefined || value === '') return null
  return (
    <div className="snapshot-strip__stat">
      <span className="snapshot-strip__stat-value">{value}</span>
      <span className="snapshot-strip__stat-label">{label}</span>
    </div>
  )
}

// Surfaces facts.resume_score/grade, facts.github_summary,
// facts.leetcode_summary, and facts.technology_breadth — none of which
// were previously rendered anywhere on the Identity page.
function ProfileSnapshotStrip({ facts }) {
  if (!facts) return null

  const gh = facts.github_summary || {}
  const lc = facts.leetcode_summary || {}
  const breadth = facts.technology_breadth || {}

  const hasResume = facts.resume_score != null || facts.resume_grade
  const hasGithub = Object.keys(gh).length > 0
  const hasLeetcode = Object.keys(lc).length > 0
  const hasBreadth = Object.keys(breadth).length > 0

  if (!hasResume && !hasGithub && !hasLeetcode && !hasBreadth) return null

  return (
    <Card className="snapshot-strip">
      {hasResume && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">Resume</span>
          <div className="snapshot-strip__stats">
            <Stat label="Score" value={facts.resume_score != null ? `${facts.resume_score}/100` : null} />
            <Stat label="Grade" value={facts.resume_grade} />
          </div>
        </div>
      )}

      {hasGithub && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">GitHub</span>
          <div className="snapshot-strip__stats">
            <Stat label="Repos synced" value={gh.repos_synced} />
            <Stat label="Commits (30d)" value={gh.total_commits_last_30_days} />
            <Stat label="Forked" value={gh.forked_repositories} />
            <Stat label="Languages" value={(gh.languages_detected || []).slice(0, 3).join(', ') || null} />
          </div>
        </div>
      )}

      {hasLeetcode && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">LeetCode</span>
          <div className="snapshot-strip__stats">
            <Stat label="Solved" value={lc.total_solved} />
            <Stat
              label="Easy / Med / Hard"
              value={lc.total_solved != null ? `${lc.easy ?? 0} / ${lc.medium ?? 0} / ${lc.hard ?? 0}` : null}
            />
            <Stat label="Contest rating" value={lc.contest_rating} />
            <Stat label="Active days (30d)" value={lc.active_days_last_30} />
          </div>
        </div>
      )}

      {hasBreadth && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">Technology Breadth</span>
          <div className="snapshot-strip__stats">
            <Stat label="Distinct technologies" value={breadth.total_distinct_technologies} />
            <Stat label="With depth data" value={breadth.technologies_with_depth_data} />
            <Stat label="Deep or better" value={breadth.deep_or_better_count} />
          </div>
        </div>
      )}
    </Card>
  )
}

export default ProfileSnapshotStrip