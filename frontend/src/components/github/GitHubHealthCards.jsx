import './GitHubHealthCards.css'

function GitHubHealthCards({ metrics }) {
  return (
    <div className="gh-health">
      {metrics.map((m) => (
        <div className="gh-health__card" key={m.label}>
          <span className="gh-health__label">{m.label}</span>
          <span className={`gh-health__value gh-health__value--${m.tone}`}>{m.value}</span>
          <span className="gh-health__tag">
            <span className={`gh-health__tag-dot gh-health__tag-dot--${m.tone}`} />
            Evidence-backed
          </span>
        </div>
      ))}
    </div>
  )
}

export default GitHubHealthCards