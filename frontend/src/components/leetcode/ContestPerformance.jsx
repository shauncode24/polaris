// frontend/src/components/leetcode/ContestPerformance.jsx
import './ContestPerformance.css'

const TREND_LABEL = {
  improving: 'Trending up',
  flat: 'Flat',
  declining: 'Trending down',
  insufficient_data: 'Not enough contests tracked yet',
  no_contests: 'No rated contests yet',
}

// global_ranking demoted per LeetCode Module Review §3: no career-actionable
// signal in isolation, so it now renders as a small footnote rather than
// a headline stat in the main grid.
function ContestPerformance({ rating, globalRanking, attendedContestsCount, trajectory }) {
  const hasRating = rating != null
  const trend = trajectory?.trend

  return (
    <section className="lc-card">
      <h3>Contest performance</h3>

      {!hasRating ? (
        <div className="lc-contest__empty-info">
          <p className="lc-empty-text">No contest history yet.</p>
          <ul className="lc-contest__benefits">
            <li>Contest rating is one of the few LeetCode signals recruiters recognize by name.</li>
            <li>Attending contests builds timed-pressure problem solving — the actual skill interviews test.</li>
            <li>5+ rated contests is enough to start showing a real trend, not just a single score.</li>
          </ul>
        </div>
      ) : (
        <>
          <div className="lc-contest__grid">
            <div className="lc-contest__stat">
              <span className="lc-contest__value">{Math.round(rating)}</span>
              <span className="lc-contest__label">Current rating</span>
            </div>
            <div className="lc-contest__stat">
              <span className="lc-contest__value">{attendedContestsCount ?? 0}</span>
              <span className="lc-contest__label">Contests attended</span>
            </div>
          </div>

          {globalRanking != null && (
            <p className="lc-contest__footnote">Global rank: #{globalRanking.toLocaleString()} (context only — not weighted in readiness)</p>
          )}

          {trend && (
            <div className={`lc-contest__trend lc-contest__trend--${trend}`}>
              <span className="lc-contest__trend-label">{TREND_LABEL[trend] || trend}</span>
              {trajectory?.change_since_first != null && trajectory?.weeks_tracked ? (
                <span className="lc-contest__trend-detail">
                  {trajectory.change_since_first > 0 ? '+' : ''}
                  {trajectory.change_since_first} rating over {trajectory.weeks_tracked} week{trajectory.weeks_tracked === 1 ? '' : 's'}
                </span>
              ) : null}
            </div>
          )}
        </>
      )}
    </section>
  )
}

export default ContestPerformance