// frontend/src/components/job-intelligence/JobIntelligenceHistoryPanel.jsx
import JobIntelligenceHistoryList from './JobIntelligenceHistoryList'
import './JobIntelligenceHistoryPanel.css'

function JobIntelligenceHistoryPanel({ items, selectedId, onSelect, loading }) {
  return (
    <aside className="ji-history-panel">
      <div className="ji-history-panel__header">
        <h3>Roles you've mapped</h3>
        <p>Load a prior extraction to compare</p>
      </div>
      {loading ? (
        <p className="jih-empty">Loading your role history…</p>
      ) : (
        <JobIntelligenceHistoryList items={items} selectedId={selectedId} onSelect={onSelect} />
      )}
    </aside>
  )
}

export default JobIntelligenceHistoryPanel