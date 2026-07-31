import './IdentityHero.css'

function IdentityHero({ narrative, generatedAt, degraded, onRefresh, refreshing }) {
  const relTime = generatedAt
    ? new Date(generatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : null

  return (
    <div className="identity-hero">
      <div className="identity-hero__top">
        <div>
          <p className="identity-hero__eyebrow">Your reconciled engineering identity</p>
          <h1 className="identity-hero__headline">{narrative?.headline || 'Not enough data yet'}</h1>
          {relTime && <p className="identity-hero__meta">Last synthesized {relTime}</p>}
        </div>
        <button type="button" className="identity-hero__btn" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? 'Synthesizing…' : 'Refresh Identity'}
        </button>
      </div>

      {narrative?.summary && <p className="identity-hero__summary">{narrative.summary}</p>}

      {degraded && (
        <p className="identity-hero__degraded">
          This synthesis used a simplified fallback — the underlying facts are still complete.
        </p>
      )}
    </div>
  )
}

export default IdentityHero