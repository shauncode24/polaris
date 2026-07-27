// frontend/src/components/interview/TargetInterviewBar.jsx
import { useEffect, useState } from 'react'
import './TargetInterviewBar.css'

function TargetInterviewBar({ targetRole, targetCompany, jobs, onSelectJob, onManualChange }) {
  const [open, setOpen] = useState(false)
  const [manualRole, setManualRole] = useState(targetRole || '')
  const [manualCompany, setManualCompany] = useState(targetCompany || '')

  useEffect(() => {
    setManualRole(targetRole || '')
    setManualCompany(targetCompany || '')
  }, [targetRole, targetCompany])

  function handleManualSave() {
    onManualChange(manualRole.trim(), manualCompany.trim())
    setOpen(false)
  }

  const label = targetRole
    ? (targetCompany ? `${targetRole} at ${targetCompany}` : targetRole)
    : 'Not set — practice will draw on your general profile'

  return (
    <div className="target-interview">
      <div className="target-interview__main">
        <span className="target-interview__label">Target interview</span>
        <span className="target-interview__value">{label}</span>
      </div>

      <div className="target-interview__control">
        <button type="button" className="target-interview__change" onClick={() => setOpen((v) => !v)}>
          Change <span className="target-interview__chevron">{open ? '▴' : '▾'}</span>
        </button>

        {open && (
          <>
            <div className="target-interview__backdrop" onClick={() => setOpen(false)} />
            <div className="target-interview__popover">
              {jobs.length > 0 && (
                <div className="target-interview__section">
                  <p className="target-interview__section-label">From an analyzed job</p>
                  {jobs.map((j) => (
                    <button
                      key={j.id}
                      type="button"
                      className="target-interview__job-option"
                      onClick={() => { onSelectJob(j); setOpen(false) }}
                    >
                      {j.role || 'Untitled role'}{j.company ? ` · ${j.company}` : ''}
                    </button>
                  ))}
                </div>
              )}
              <div className="target-interview__section">
                <p className="target-interview__section-label">Manual</p>
                <input
                  className="target-interview__input"
                  placeholder="Target role"
                  value={manualRole}
                  onChange={(e) => setManualRole(e.target.value)}
                />
                <input
                  className="target-interview__input"
                  placeholder="Company (optional)"
                  value={manualCompany}
                  onChange={(e) => setManualCompany(e.target.value)}
                />
                <button type="button" className="target-interview__save" onClick={handleManualSave}>
                  Save
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default TargetInterviewBar