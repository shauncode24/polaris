// frontend/src/components/leetcode/PracticeOverview.jsx
// Merges Practice Heatmap + Contest Performance + Difficulty Distribution
// into one compact card (Review §"What Should Be Merged").
import './PracticeOverview.css'

function buildIntensityGrid(activeDaysLast30) {
  const cells = 28
  const activeRatio = Math.min(1, (activeDaysLast30 || 0) / 30)
  const seedBase = activeDaysLast30 || 0
  return Array.from({ length: cells }, (_, i) => {
    const pseudo = Math.abs(Math.sin(i * 12.9898 + seedBase) * 43758.5453) % 1
    if (pseudo < activeRatio * 0.35) return 3
    if (pseudo < activeRatio * 0.65) return 2
    if (pseudo < activeRatio) return 1
    return 0
  })
}

const TREND_LABEL = {
  improving: 'Trending up',
  flat: 'Flat',
  declining: 'Trending down',
  insufficient_data: 'Not enough contests yet',
  no_contests: 'No rated contests yet',
}

function PracticeOverview({
  currentStreak, longestStreak, activeDaysLast30, preferredDifficulty, averageSessionLength,
  easy, medium, hard,
  rating, attendedContestsCount, trajectory,
}) {
  const grid = buildIntensityGrid(activeDaysLast30)
  const totalDiff = (easy || 0) + (medium || 0) + (hard || 0)
  const pct = (n) => (totalDiff > 0 ? Math.round((n / totalDiff) * 100) : 0)
  const trend = trajectory?.trend

  return (
    <section className="lc-card po-card">
      <h3>Practice overview</h3>

      <div className="po-heatmap-row">
        <div className="po-heatmap-grid">
          {grid.map((level, i) => <span key={i} className={`po-cell po-cell--${level}`} />)}
        </div>
        <div className="po-heatmap-stats">
          <span className="po-stat"><strong>{currentStreak > 0 ? currentStreak : 0}</strong>day streak</span>
          <span className="po-stat"><strong>{longestStreak || 0}</strong>longest</span>
          <span className="po-stat"><strong>{activeDaysLast30 || 0}</strong>active (30d)</span>
        </div>
      </div>
      {((preferredDifficulty && preferredDifficulty !== 'None') || averageSessionLength != null) && (
        <p className="po-habits">
          {preferredDifficulty && preferredDifficulty !== 'None' && <>Prefers <strong>{preferredDifficulty}</strong></>}
          {preferredDifficulty && preferredDifficulty !== 'None' && averageSessionLength != null && ' · '}
          {averageSessionLength != null && <>~{averageSessionLength}/day active</>}
        </p>
      )}

      <div className="po-divider" />

      <div className="po-row-2">
        <div className="po-diff">
          <span className="po-label">Difficulty</span>
          {totalDiff === 0 ? (
            <p className="lc-empty-text">No problems solved yet.</p>
          ) : (
            <>
              <div className="po-diff-bar">
                <span className="po-seg po-seg--easy" style={{ width: `${pct(easy)}%` }} />
                <span className="po-seg po-seg--medium" style={{ width: `${pct(medium)}%` }} />
                <span className="po-seg po-seg--hard" style={{ width: `${pct(hard)}%` }} />
              </div>
              <div className="po-diff-nums">
                <span className="po-diff-num po-diff-num--easy">{easy} Easy</span>
                <span className="po-diff-num po-diff-num--medium">{medium} Med</span>
                <span className="po-diff-num po-diff-num--hard">{hard} Hard</span>
              </div>
            </>
          )}
        </div>

        <div className="po-contest">
          <span className="po-label">Contests</span>
          {rating == null ? (
            <p className="lc-empty-text">No contest history yet.</p>
          ) : (
            <>
              <div className="po-contest-nums">
                <span><strong>{Math.round(rating)}</strong> rating</span>
                <span><strong>{attendedContestsCount ?? 0}</strong> attended</span>
              </div>
              {trend && (
                <span className={`po-trend po-trend--${trend}`}>
                  {TREND_LABEL[trend] || trend}
                  {trajectory?.change_since_first != null && trajectory?.weeks_tracked
                    ? ` (${trajectory.change_since_first > 0 ? '+' : ''}${trajectory.change_since_first} / ${trajectory.weeks_tracked}w)`
                    : ''}
                </span>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  )
}

export default PracticeOverview