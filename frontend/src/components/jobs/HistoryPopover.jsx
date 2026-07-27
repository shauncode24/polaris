import { useEffect, useRef, useState } from 'react'
import AnalysisHistoryList from './AnalysisHistoryList'
import './HistoryPopover.css'

function IconClock({ size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </svg>
  )
}

function HistoryPopover({ items, selectedId, onSelect, loading }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function handleSelect(id) {
    onSelect(id)
    setOpen(false)
  }

  return (
    <div className="history-popover" ref={rootRef}>
      <button type="button" className="history-popover__trigger" onClick={() => setOpen((v) => !v)}>
        <IconClock size={15} />
        History
        {items?.length > 0 && <span className="history-popover__count">{items.length}</span>}
      </button>

      {open && (
        <div className="history-popover__panel">
          <div className="history-popover__panel-header">
            <h4>Past analyses</h4>
            <p>Load a prior report to compare</p>
          </div>
          <div className="history-popover__panel-body">
            {loading ? (
              <p className="ah-empty">Loading…</p>
            ) : (
              <AnalysisHistoryList items={items} selectedId={selectedId} onSelect={handleSelect} />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default HistoryPopover