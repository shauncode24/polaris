// frontend/src/components/leetcode/ContestPerformance.jsx
import './ContestPerformance.css'

function ContestPerformance({ rating, globalRanking, attendedContestsCount }) {
  const hasRating = rating != null

  return (
    <section className="lc-card">
      <h3>Contest performance</h3>

      {!hasRating ? (
        <p className="lc-empty-text">No contest history yet — attend a rated contest to unlock this.</p>
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