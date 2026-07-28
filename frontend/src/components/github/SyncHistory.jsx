import { formatDayLabel } from '../../utils/formatRelativeTime'
import './SyncHistory.css'

function SyncHistory({ syncedAt, summary }) {
  return (
    <section className="gh-sync-history">
      <h2>Sync history</h2>
      <div className="gh-sync-history__item">
        <span className="gh-sync-history__when">{formatDayLabel(syncedAt)}</span>
        <span className="gh-sync-history__text">
          {summary?.repos_synced ?? 0} repositories synced
          {summary?.new_repositories ? ` · ${summary.new_repositories} new` : ''}
          {summary?.updated_repositories ? ` · ${summary.updated_repositories} updated` : ''}
        </span>
      </div>
    </section>
  )
}

export default SyncHistory