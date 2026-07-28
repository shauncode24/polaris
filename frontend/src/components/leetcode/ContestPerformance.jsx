// frontend/src/components/leetcode/ContestPerformance.jsx
import './ContestPerformance.css'

function ContestPerformance({ rating, globalRanking, attendedContestsCount }) {
  const hasRating = rating != null

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
        <div className="lc-contest__grid">
          <div className="lc-contest__stat">
            <span className="lc-contest__value">{Math.round(rating)}</span>
            <span className="lc-contest__label">Current rating</span>
          </div>
          <div className="lc-contest__stat">
            <span className="lc-contest__value">{attendedContestsCount ?? 0}</span>
            <span className="lc-contest__label">Contests attended</span>
          </div>
          {globalRanking != null && (
            <div className="lc-contest__stat lc-contest__stat--wide">
              <span className="lc-contest__value">#{globalRanking.toLocaleString()}</span>
              <span className="lc-contest__label">Global rank</span>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export default ContestPerformance