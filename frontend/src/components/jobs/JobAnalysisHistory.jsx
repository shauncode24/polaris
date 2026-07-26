import './JobAnalysisHistory.css'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function JobAnalysisHistory({ items, selectedId, onSelect, loading }) {
  if (loading) {
    return <p className="jd-history__empty">Loading your past analyses…</p>
  }

  if (!items || items.length === 0) {
    return <p className="jd-history__empty">No job analyses yet — run your first one above.</p>
  }

  return (
    <div className="jd-history">
      <h3 className="jd-history__title">Past Analyses</h3>
      <ul className="jd-history__list">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={`jd-history__item ${item.id === selectedId ? 'jd-history__item--active' : ''}`}
              onClick={() => onSelect(item.id)}
            >
              <div className="jd-history__item-main">
                <span className="jd-history__item-role">
                  {item.role || 'Untitled role'}
                  {item.company ? ` · ${item.company}` : ''}
                </span>
                <span className="jd-history__item-date">{formatDate(item.created_at)}</span>
              </div>
              {item.overall_match_percentage != null && (
                <span className="jd-history__item-score">
                  {Math.round(item.overall_match_percentage)}%
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default JobAnalysisHistory