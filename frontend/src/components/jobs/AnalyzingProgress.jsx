import './AnalyzingProgress.css'

function AnalyzingProgress({ stages, activeIndex, title = 'Analyzing this role…' }) {
  const percent = Math.round(((activeIndex + 1) / stages.length) * 100)

  return (
    <div className="analyzing-progress">
      <div className="analyzing-progress__header">
        <h3>{title}</h3>
        <span className="analyzing-progress__pct">{percent}%</span>
      </div>

      <div className="analyzing-progress__track">
        <div className="analyzing-progress__fill" style={{ width: `${percent}%` }} />
      </div>

      <ul className="analyzing-progress__list">
        {stages.map((label, i) => {
          const state = i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending'
          return (
            <li key={label} className={`analyzing-progress__item analyzing-progress__item--${state}`}>
              <span className="analyzing-progress__icon">
                {state === 'done' && (
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12.5l4.5 4.5L19 7.5" />
                  </svg>
                )}
                {state === 'active' && <span className="analyzing-progress__spinner" />}
                {state === 'pending' && <span className="analyzing-progress__dot" />}
              </span>
              <span>{label}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default AnalyzingProgress