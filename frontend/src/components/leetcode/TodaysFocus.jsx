// frontend/src/components/leetcode/TodaysFocus.jsx
import './TodaysFocus.css'

const MINUTES_PER_RECOMMENDATION = 30

function TodaysFocus({ recommendations }) {
  const items = recommendations || []
  const estimatedMinutes = items.length * MINUTES_PER_RECOMMENDATION

  return (
    <section className="lc-card lc-focus">
      <h3>Today's focus</h3>

      {items.length === 0 ? (
        <p className="lc-empty-text">No recommendations yet — sync more practice history to unlock this.</p>
      ) : (
        <>
          <ul className="lc-focus__list">
            {items.map((r, i) => (
              <li key={i} className="lc-focus__item">
                <span className={`lc-focus__priority lc-focus__priority--${(r.priority || 'medium').toLowerCase()}`} />
                {r.action}
              </li>
            ))}
          </ul>
          <p className="lc-focus__estimate">Estimated time · ~{estimatedMinutes} minutes</p>
          <button type="button" className="lc-focus__cta">Start practice</button>
        </>
      )}
    </section>
  )
}

export default TodaysFocus