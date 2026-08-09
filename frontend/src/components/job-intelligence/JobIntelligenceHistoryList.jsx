// frontend/src/components/job-intelligence/JobIntelligenceHistoryList.jsx
import './JobIntelligenceHistoryList.css'

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

const SENIORITY_LABELS = {
  intern: 'Intern',
  junior: 'Junior',
  mid: 'Mid',
  senior: 'Senior',
  staff: 'Staff+',
  unspecified: '—',
}

function JobIntelligenceHistoryList({ items, selectedId, onSelect, emptyLabel = 'No roles extracted yet.' }) {
  if (!items || items.length === 0) {
    return <p className="jih-empty">{emptyLabel}</p>
  }

  return (
    <ul className="jih-list">
      {items.map((item) => {
        const active = item.id === selectedId
        return (
          <li key={item.id}>
            <button
              type="button"
              className={`jih-item ${active ? 'jih-item--active' : ''}`}
              onClick={() => onSelect(item.id)}
            >
              <div className="jih-item__main">
                <span className="jih-item__role">{item.role || 'Untitled role'}</span>
                <span className="jih-item__company">{item.company || '—'}</span>
                <span className="jih-item__date">{formatDate(item.created_at)}</span>
              </div>
              <span className="jih-badge">{SENIORITY_LABELS[item.seniority_level] || '—'}</span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export default JobIntelligenceHistoryList