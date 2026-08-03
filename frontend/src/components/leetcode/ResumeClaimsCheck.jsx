// frontend/src/components/leetcode/ResumeClaimsCheck.jsx
// Redesigned as a compact "Resume Impact" card (Review §"What Should Be
// Merged") — a one-line verdict plus flagged items, not a full section.
import './ResumeClaimsCheck.css'

function ResumeClaimsCheck({ resumeClaims }) {
  if (!resumeClaims) {
    return (
      <section className="lc-card">
        <h3>Resume impact</h3>
        <p className="lc-empty-text">Upload a resume and sync LeetCode to cross-check DSA claims against real evidence.</p>
      </section>
    )
  }

  const { claims_found, mismatches, opportunities } = resumeClaims
  const nothingToShow = claims_found.length === 0 && mismatches.length === 0 && opportunities.length === 0
  const isClean = mismatches.length === 0 && !nothingToShow

  return (
    <section className="lc-card">
      <h3>Resume impact</h3>

      {nothingToShow ? (
        <p className="lc-empty-text">No DSA-related claims detected on your resume, and no strong evidence yet to flag as a missed opportunity.</p>
      ) : (
        <div className="rcc-list">
          <p className={`rcc-verdict ${isClean ? 'rcc-verdict--good' : 'rcc-verdict--warn'}`}>
            {isClean
              ? '✓ Claims verified — no DSA inconsistencies detected.'
              : `⚠ ${mismatches.length} claim${mismatches.length === 1 ? '' : 's'} not backed by solved-problem evidence.`}
          </p>

          {claims_found.length > 0 && (
            <div className="rcc-row">
              <span className="rcc-row__label">Claims found</span>
              <div className="rcc-pills">
                {claims_found.map((c) => <span key={c} className="rcc-pill">{c}</span>)}
              </div>
            </div>
          )}
          {mismatches.map((m, i) => (
            <p key={`m-${i}`} className="rcc-text rcc-text--warn">{m}</p>
          ))}
          {opportunities.map((o, i) => (
            <p key={`o-${i}`} className="rcc-text rcc-text--good">{o}</p>
          ))}
        </div>
      )}
    </section>
  )
}

export default ResumeClaimsCheck