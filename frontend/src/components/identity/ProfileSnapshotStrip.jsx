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

// Trimmed to headline numbers only — the full breakdown (languages,
// contest rating, active days, "technologies with depth data", etc.)
// already lives on the Resume/GitHub/LeetCode pages. This strip exists
// to answer "what did Polaris look at", not to re-report those pages.
function ProfileSnapshotStrip({ facts }) {
  if (!facts) return null

  const gh = facts.github_summary || {}
  const lc = facts.leetcode_summary || {}
  const breadth = facts.technology_breadth || {}

  const hasResume = facts.resume_score != null || facts.resume_grade
  const hasGithub = gh.repos_synced != null || gh.total_commits_last_30_days != null
  const hasLeetcode = lc.total_solved != null
  const hasBreadth = breadth.total_distinct_technologies != null

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
            <Stat label="Commits (30d)" value={gh.total_commits_last_30_days} />
            <Stat label="Repos synced" value={gh.repos_synced} />
          </div>
        </div>
      )}

      {hasLeetcode && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">LeetCode</span>
          <div className="snapshot-strip__stats">
            <Stat label="Solved" value={lc.total_solved} />
          </div>
        </div>
      )}

      {hasBreadth && (
        <div className="snapshot-strip__group">
          <span className="snapshot-strip__group-title">Tech Stack</span>
          <div className="snapshot-strip__stats">
            <Stat label="Technologies" value={breadth.total_distinct_technologies} />
          </div>
        </div>
      )}
    </Card>
  )
}

export default ProfileSnapshotStrip