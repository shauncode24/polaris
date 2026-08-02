import { useState, useRef, useEffect } from 'react'
import './VersionHistoryDrawer.css'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function VersionHistoryDrawer({ versions = [] }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const current = versions.find(v => v.is_current) || versions[versions.length - 1]

  return (
    <div className="vhd" ref={ref}>
      <button type="button" className="vhd__trigger" onClick={() => setOpen(v => !v)}>
        {current?.version || 'v1'}
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="vhd__panel">
          <div className="vhd__panel-title">Version History</div>
          {versions.length === 0 ? (
            <div className="vhd__empty">No upload history yet.</div>
          ) : (
            versions.map((v) => (
              <div className="vhd__item" key={v.id}>
                <div className={`vhd__dot ${v.is_current ? 'vhd__dot--current' : ''}`} />
                <div className="vhd__info">
                  <div className="vhd__ver">
                    {v.version}
                    {v.is_current && <span className="vhd__current-badge">Current</span>}
                  </div>
                  <div className="vhd__filename">{v.filename || 'resume.pdf'}</div>
                </div>
                <div className="vhd__date">{formatDate(v.created_at)}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}