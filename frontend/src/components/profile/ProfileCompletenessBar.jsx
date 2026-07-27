import './ProfileCompletenessBar.css'

const SOURCES = [
  { key: 'resume', label: 'Resume' },
  { key: 'github', label: 'GitHub' },
  { key: 'leetcode', label: 'LeetCode' },
  { key: 'certificates', label: 'Certificates', optional: true },
  { key: 'goal', label: 'Goals', optional: true },
]

function computeCompleteness(results) {
  let score = 0
  if (results.resume) score += 33
  if (results.github) score += 27
  if (results.leetcode) score += 20
  if (results.certificates?.length > 0) score += 10
  if (results.goal) score += 10
  return Math.min(100, score)
}

function SourceItem({ source, connected }) {
  return (
    <div className="pcb__source">
      {connected ? (
        <span className="pcb__source-check" aria-label="Connected">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </span>
      ) : (
        <span className="pcb__source-plus" aria-label="Not connected">+</span>
      )}
      <div>
        <div className="pcb__source-label">{source.label}</div>
        <div className={`pcb__source-sub ${connected ? 'pcb__source-sub--ready' : ''}`}>
          {connected ? 'Ready' : 'Add now'}
        </div>
      </div>
    </div>
  )
}

function ProfileCompletenessBar({ results }) {
  const pct = computeCompleteness(results)

  return (
    <div className="pcb">
      <div className="pcb__header">
        <div>
          <div className="pcb__title">Profile completeness</div>
          <div className="pcb__subtitle">Keep every evidence source findable and current.</div>
        </div>
        <div className="pcb__pct">{pct}%</div>
      </div>

      <div className="pcb__bar-track">
        <div className="pcb__bar-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="pcb__sources">
        {SOURCES.map((s) => {
          const connected =
            s.key === 'certificates'
              ? results.certificates?.length > 0
              : Boolean(results[s.key])
          return (
            <SourceItem key={s.key} source={s} connected={connected} />
          )
        })}
      </div>
    </div>
  )
}

export default ProfileCompletenessBar
