// frontend/src/components/job-intelligence/AnalyzingJobIntelligence.jsx
import './AnalyzingJobIntelligence.css'

function AnalyzingJobIntelligence({ stages, activeIndex, title = 'Understanding this role…' }) {
  const percent = Math.round(((activeIndex + 1) / stages.length) * 100)

  return (
    <div className="ji-analyzing">
      <div className="ji-analyzing__header">
        <h3>{title}</h3>
        <span className="ji-analyzing__pct">{percent}%</span>
      </div>

      <div className="ji-analyzing__track">
        <div className="ji-analyzing__fill" style={{ width: `${percent}%` }} />
      </div>

      <ul className="ji-analyzing__list">
        {stages.map((label, i) => {
          const state = i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending'
          return (
            <li key={label} className={`ji-analyzing__item ji-analyzing__item--${state}`}>
              <span className="ji-analyzing__icon">
                {state === 'done' && (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                )}
                {state === 'active' && <span className="ji-analyzing__spinner" />}
                {state === 'pending' && <span className="ji-analyzing__dot" />}
              </span>
              <span>{label}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default AnalyzingJobIntelligence