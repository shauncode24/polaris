// frontend/src/components/leetcode/DifficultyDistribution.jsx
import './DifficultyDistribution.css'

// The templated insightText paragraph was removed here (LeetCode Module
// Review §3): it was restating facts, not producing real inference. That
// interpretation now lives in the AI Coach panel's "interview_coach"
// narrative, which has the fuller context (quadrant, company readiness,
// resume claims) to say something real about difficulty mix.
function DifficultyDistribution({ easy, medium, hard }) {
  const total = (easy || 0) + (medium || 0) + (hard || 0)
  const pct = (n) => (total > 0 ? Math.round((n / total) * 100) : 0)

  return (
    <section className="lc-card">
      <h3>Difficulty distribution</h3>

      {total === 0 ? (
        <p className="lc-empty-text">No problems solved yet.</p>
      ) : (
        <>
          <div className="lc-diff__bar">
            <span className="lc-diff__seg lc-diff__seg--easy" style={{ width: `${pct(easy)}%` }} />
            <span className="lc-diff__seg lc-diff__seg--medium" style={{ width: `${pct(medium)}%` }} />
            <span className="lc-diff__seg lc-diff__seg--hard" style={{ width: `${pct(hard)}%` }} />
          </div>

          <div className="lc-diff__stats">
            <div className="lc-diff__stat">
              <span className="lc-diff__value lc-diff__value--easy">{easy}</span>
              <span className="lc-diff__label">Easy</span>
            </div>
            <div className="lc-diff__stat">
              <span className="lc-diff__value lc-diff__value--medium">{medium}</span>
              <span className="lc-diff__label">Medium</span>
            </div>
            <div className="lc-diff__stat">
              <span className="lc-diff__value lc-diff__value--hard">{hard}</span>
              <span className="lc-diff__label">Hard</span>
            </div>
          </div>
        </>
      )}
    </section>
  )
}

export default DifficultyDistribution