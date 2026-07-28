import { formatDayLabel } from '../../utils/formatRelativeTime'
import './ActivityTimeline.css'

function ActivityTimeline({ repositories }) {
  const entries = [...repositories]
    .filter((r) => r.pushed_at)
    .sort((a, b) => new Date(b.pushed_at) - new Date(a.pushed_at))
    .slice(0, 6)

  return (
    <section className="gh-timeline">
      <h2>Activity timeline</h2>
      {entries.length === 0 ? (
        <p className="gh-timeline__empty">No recent activity synced yet.</p>
      ) : (
        <ul className="gh-timeline__list">
          {entries.map((repo) => (
            <li key={repo.name} className="gh-timeline__item">
              <span className="gh-timeline__when">{formatDayLabel(repo.pushed_at)}</span>
              <span className="gh-timeline__text">
                {repo.is_new ? 'Created' : 'Updated'} <strong>{repo.name}</strong>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default ActivityTimeline