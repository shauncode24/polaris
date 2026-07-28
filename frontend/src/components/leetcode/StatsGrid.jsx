// frontend/src/components/leetcode/StatsGrid.jsx
import './StatsGrid.css'

function StatsGrid({ stats }) {
  return (
    <div className="lc-stats">
      {stats.map((s) => (
        <div className="lc-stats__card" key={s.label}>
          <span className="lc-stats__value">{s.value}</span>
          <span className="lc-stats__label">{s.label}</span>
        </div>
      ))}
    </div>
  )
}

export default StatsGrid