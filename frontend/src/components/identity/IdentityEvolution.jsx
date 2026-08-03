// frontend/src/components/identity/IdentityEvolution.jsx
import './IdentityEvolution.css'

function formatShortDate(dateStr) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// Reuses GET /identity/history (already fetched for IdentityHistoryPanel)
// to build a compact "how has Polaris's read on me changed" chain —
// replacing a long, developer-facing snapshot log with the one thing a
// user actually wants from that history: did my headline change.
function IdentityEvolution({ history = [], currentNarrative, currentGeneratedAt }) {
  const points = [...history]
    .filter((h) => h?.narrative?.headline)
    .sort((a, b) => new Date(a.generated_at) - new Date(b.generated_at))
    .map((h) => ({ headline: h.narrative.headline, generated_at: h.generated_at }))

  if (currentNarrative?.headline) {
    points.push({ headline: currentNarrative.headline, generated_at: currentGeneratedAt })
  }

  const deduped = []
  for (const p of points) {
    if (deduped.length === 0 || deduped[deduped.length - 1].headline !== p.headline) {
      deduped.push(p)
    } else {
      deduped[deduped.length - 1] = p
    }
  }

  const chain = deduped.slice(-4)

  if (chain.length < 2) return null

  return (
    <div className="evolution">
      <span className="evolution__title">Identity Evolution</span>
      <div className="evolution__chain">
        {chain.map((p, i) => (
          <div className="evolution__point" key={`${p.headline}-${i}`}>
            <div className={`evolution__bubble ${i === chain.length - 1 ? 'evolution__bubble--current' : ''}`}>
              <span className="evolution__headline">{p.headline}</span>
              <span className="evolution__date">{formatShortDate(p.generated_at)}</span>
            </div>
            {i < chain.length - 1 && <span className="evolution__arrow">→</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

export default IdentityEvolution