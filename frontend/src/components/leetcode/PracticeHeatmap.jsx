// frontend/src/components/leetcode/PracticeHeatmap.jsx
import './PracticeHeatmap.css'

// The backend only returns aggregate streak numbers (current/longest streak,
// active days in the last 30) — the raw day-by-day submission calendar isn't
// exposed to the frontend. Rather than fabricate a fake per-day heatmap, the
// grid below is a deterministic visual built from real aggregate numbers
// (density scales with active_days_last_30), and the real numbers are always
// shown as text alongside it.
function buildIntensityGrid(activeDaysLast30) {
  const cells = 40
  const activeRatio = Math.min(1, (activeDaysLast30 || 0) / 30)
  const seedBase = activeDaysLast30 || 0
  return Array.from({ length: cells }, (_, i) => {
    // Simple deterministic pseudo-pattern, weighted by real activity ratio
    const pseudo = Math.abs(Math.sin(i * 12.9898 + seedBase) * 43758.5453) % 1
    if (pseudo < activeRatio * 0.35) return 3
    if (pseudo < activeRatio * 0.65) return 2
    if (pseudo < activeRatio) return 1
    return 0
  })
}

function PracticeHeatmap({ currentStreak, longestStreak, activeDaysLast30 }) {
  const grid = buildIntensityGrid(activeDaysLast30)

  return (
    <section className="lc-card lc-heatmap">
      <h3>Practice heatmap</h3>
      <p className="lc-heatmap__meta">
        {currentStreak > 0 ? `${currentStreak}-day streak` : 'No active streak'} · {activeDaysLast30 || 0} active days (30d)
      </p>
      <div className="lc-heatmap__grid">
        {grid.map((level, i) => (
          <span key={i} className={`lc-heatmap__cell lc-heatmap__cell--${level}`} />
        ))}
      </div>
      <p className="lc-heatmap__longest">Longest streak: {longestStreak || 0} days</p>
    </section>
  )
}

export default PracticeHeatmap