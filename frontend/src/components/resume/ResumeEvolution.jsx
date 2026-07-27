import './ResumeEvolution.css'

export default function ResumeEvolution() {
  return (
    <div className="revo">
      <div className="revo__header">
        <span className="revo__title">Resume Evolution</span>
        <span className="revo__badge">Coming Soon</span>
      </div>
      <div className="revo__body">
        <div className="revo__icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
            <polyline points="17 6 23 6 23 12" />
          </svg>
        </div>
        <p className="revo__caption">
          Track how your resume has evolved across uploads — new skills, improved bullets, and growth over time.
        </p>
        <span className="revo__sub">GitHub + upload history analysis — data pending</span>
      </div>
    </div>
  )
}
