import AnalysisHistoryList from './AnalysisHistoryList'
import './PastAnalysesPanel.css'

function PastAnalysesPanel({ items, selectedId, onSelect, loading }) {
  return (
    <aside className="past-analyses">
      <div className="past-analyses__header">
        <h3>Past analyses</h3>
        <p>Load a prior report to compare</p>
      </div>
      {loading ? (
        <p className="ah-empty">Loading your past analyses…</p>
      ) : (
        <AnalysisHistoryList items={items} selectedId={selectedId} onSelect={onSelect} />
      )}
    </aside>
  )
}

export default PastAnalysesPanel