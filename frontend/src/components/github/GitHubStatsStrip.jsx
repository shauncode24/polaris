import './GitHubStatsStrip.css'

function GitHubStatsStrip({ stats }) {
  return (
    <div className="gh-stats">
      {stats.map((s) => (
        <div className="gh-stats__card" key={s.label}>
          <span className="gh-stats__value">{s.value}</span>
          <span className="gh-stats__label">{s.label}</span>
        </div>
      ))}
    </div>
  )
}

export default GitHubStatsStrip