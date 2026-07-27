import './AnalysisHistoryList.css'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function tierClass(pct) {
  if (pct == null) return 'ah-badge--neutral'
  if (pct >= 75) return 'ah-badge--strong'
  if (pct >= 50) return 'ah-badge--partial'
  return 'ah-badge--weak'
}

function AnalysisHistoryList({ items, selectedId, onSelect, emptyLabel = 'No analyses yet.' }) {
  if (!items || items.length === 0) {
    return <p className="ah-empty">{emptyLabel}</p>
  }

  return (
    <ul className="ah-list">
      {items.map((item) => {
        const active = item.id === selectedId
        const pct = item.overall_match_percentage
        return (
          <li key={item.id}>
            <button
              type="button"
              className={`ah-item ${active ? 'ah-item--active' : ''}`}
              onClick={() => onSelect(item.id)}
            >
              <div className="ah-item__main">
                <span className="ah-item__role">{item.role || 'Untitled role'}</span>
                <span className="ah-item__company">{item.company || '—'}</span>
                <span className="ah-item__date">{formatDate(item.created_at)}</span>
              </div>
              {pct != null && (
                <span className={`ah-badge ${active ? 'ah-badge--active' : tierClass(pct)}`}>
                  {Math.round(pct)}
                </span>
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export default AnalysisHistoryList