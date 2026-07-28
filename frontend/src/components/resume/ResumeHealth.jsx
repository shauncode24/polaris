import './ResumeHealth.css'

const SEV_ICON = {
  high: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  medium: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  low: (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" />
    </svg>
  ),
}

export default function ResumeHealth({ ats_flags = [] }) {
  const allGood = ats_flags.length === 0

  return (
    <div className="rh-checks__body">
      {allGood ? (
        <div className="rh-checks__all-good">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
          </svg>
          No ATS issues detected — great work!
        </div>
      ) : (
        ats_flags.map((flag, i) => (
          <div className="rh-checks__item" key={i}>
            <div className={`rh-checks__icon rh-checks__icon--${flag.severity}`}>
              {SEV_ICON[flag.severity] || SEV_ICON.low}
            </div>
            <div>
              <div className="rh-checks__detail">{flag.detail}</div>
              <div className="rh-checks__sev">{flag.severity} severity</div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
