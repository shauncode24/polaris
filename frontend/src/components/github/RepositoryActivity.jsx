import './RepositoryActivity.css'

function toneForCommits(commits, max) {
  if (max === 0) return 'low'
  const ratio = commits / max
  if (ratio >= 0.66) return 'high'
  if (ratio >= 0.33) return 'medium'
  return 'low'
}

function RepositoryActivity({ repositories }) {
  const ranked = [...repositories]
    .filter((r) => (r.commits_last_30_days || 0) > 0)
    .sort((a, b) => (b.commits_last_30_days || 0) - (a.commits_last_30_days || 0))
    .slice(0, 8)

  const max = ranked.length > 0 ? ranked[0].commits_last_30_days : 0

  return (
    <div className="gh-activity">
      <div className="gh-activity__header">
        <div>
          <h2>Repository activity</h2>
          <p>Commits in the last 30 days, by repository</p>
        </div>
        {max > 0 && <span className="gh-activity__badge">● Active</span>}
      </div>

      {ranked.length === 0 ? (
        <p className="gh-activity__empty">No commit activity in the last 30 days.</p>
      ) : (
        <ul className="gh-activity__list">
          {ranked.map((repo) => (
            <li key={repo.name} className="gh-activity__row">
              <span className="gh-activity__name">{repo.name}</span>
              <div className="gh-activity__track">
                <div
                  className={`gh-activity__bar gh-activity__bar--${toneForCommits(repo.commits_last_30_days, max)}`}
                  style={{ width: `${Math.max(6, Math.round((repo.commits_last_30_days / max) * 100))}%` }}
                />
              </div>
              <span className="gh-activity__count">{repo.commits_last_30_days}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default RepositoryActivity