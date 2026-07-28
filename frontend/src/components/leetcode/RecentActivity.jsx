// frontend/src/components/leetcode/RecentActivity.jsx
// LeetCode's unofficial API doesn't give us a per-problem submission feed
// (only tag-level solved counts), so rather than invent fake "Two Sum,
// Easy, 2 mins ago" rows, this renders what the sync pipeline actually
// diffed: which skills got reinforced/newly evidenced this sync, plus any
// mastery-level changes since the previous sync.
import './RecentActivity.css'

function RecentActivity({ skillEvidenceDetail, progress }) {
  const reinforced = skillEvidenceDetail?.reinforced || []
  const newSkills = skillEvidenceDetail?.new || []
  const masteryChanges = progress?.mastery_changes || []
  const newProblems = progress?.new_problems

  const hasAnything = reinforced.length > 0 || newSkills.length > 0 || masteryChanges.length > 0

  return (
    <section className="lc-card">
      <h2>Recent activity</h2>
      <p className="lc-card__lead">What changed since your last sync.</p>

      {!hasAnything ? (
        <p className="lc-empty-text">
          {newProblems == null
            ? 'This is your first sync — come back after your next one to see real deltas.'
            : 'No meaningful changes detected since your last sync.'}
        </p>
      ) : (
        <div className="lc-activity">
          {newProblems != null && (
            <p className="lc-activity__summary">
              <strong>+{newProblems}</strong> problem{newProblems === 1 ? '' : 's'} solved since last sync.
            </p>
          )}

          {masteryChanges.length > 0 && (
            <div className="lc-activity__group">
              <h4>Mastery changes</h4>
              <ul>
                {masteryChanges.map((c) => (
                  <li key={c.topic}>
                    <strong>{c.topic}</strong>: {c.from} → {c.to}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {newSkills.length > 0 && (
            <div className="lc-activity__group">
              <h4>New skill evidence</h4>
              <div className="lc-activity__pills">
                {newSkills.map((s) => <span key={s} className="lc-activity__pill">{s.replace(/_/g, ' ')}</span>)}
              </div>
            </div>
          )}

          {reinforced.length > 0 && (
            <div className="lc-activity__group">
              <h4>Reinforced skills</h4>
              <div className="lc-activity__pills">
                {reinforced.map((s) => <span key={s} className="lc-activity__pill">{s.replace(/_/g, ' ')}</span>)}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export default RecentActivity