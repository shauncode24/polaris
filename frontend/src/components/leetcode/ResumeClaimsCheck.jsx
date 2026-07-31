import './ResumeClaimsCheck.css'

function ResumeClaimsCheck({ resumeClaims }) {
  if (!resumeClaims) {
    return (
      <section className="lc-card">
        <h3>Resume vs. LeetCode evidence</h3>
        <p className="lc-empty-text">Upload a resume and sync LeetCode to cross-check DSA claims against real evidence.</p>
      </section>
    )
  }

  const { claims_found, mismatches, opportunities } = resumeClaims
  const nothingToShow = claims_found.length === 0 && mismatches.length === 0 && opportunities.length === 0

  return (
    <section className="lc-card">
      <h3>Resume vs. LeetCode evidence</h3>
      <p className="lc-card__lead">Do the DSA claims on your resume hold up against what you've actually solved?</p>

      {nothingToShow ? (
        <p className="lc-empty-text">No DSA-related claims detected on your resume, and no strong LeetCode evidence yet to flag as a missed opportunity.</p>
      ) : (
        <div className="rcc-list">
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