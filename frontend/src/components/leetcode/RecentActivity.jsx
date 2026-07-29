import './RecentActivity.css'

function RecentActivity({ skillEvidenceDetail, progress, planAdherence }) {
  const reinforced = skillEvidenceDetail?.reinforced || []
  const newSkills = skillEvidenceDetail?.new || []
  const masteryChanges = progress?.mastery_changes || []
  const newProblems = progress?.new_problems
  const adherence = planAdherence || []

  const events = []
  if (newProblems) events.push({ type: 'count', text: `+${newProblems} problem${newProblems === 1 ? '' : 's'} solved since last sync` })
  masteryChanges.forEach((c) => events.push({ type: 'mastery', text: `${c.topic}: ${c.from} → ${c.to}` }))
  newSkills.forEach((s) => events.push({ type: 'new', text: `New evidence: ${s.replace(/_/g, ' ')}` }))
  reinforced.forEach((s) => events.push({ type: 'reinforced', text: `Reinforced: ${s.replace(/_/g, ' ')}` }))

  return (
    <section className="lc-card">
      <h2>Recent activity</h2>
      <p className="lc-card__lead">What changed since your last sync.</p>

      {events.length === 0 ? (
        <p className="lc-empty-text">
          {newProblems == null
            ? 'This is your first sync — come back after your next one to see real deltas.'
            : 'No meaningful changes detected since your last sync.'}
        </p>
      ) : (
        <ul className="lc-timeline">
          {events.map((e, i) => (
            <li key={i} className={`lc-timeline__item lc-timeline__item--${e.type}`}>
              <span className="lc-timeline__dot" />
              {e.text}
            </li>
          ))}
        </ul>
      )}

      {adherence.length > 0 && (
        <div className="lc-adherence">
          <span className="lc-adherence__label">Did you follow the coach's last advice?</span>
          <ul className="lc-adherence__list">
            {adherence.map((a) => (
              <li key={a.topic} className={`lc-adherence__item lc-adherence__item--${a.status}`}>
                <span className="lc-adherence__topic">{a.topic}</span>
                <span className="lc-adherence__status">
                  {a.status === 'followed'
                    ? `+${a.new_problems_since_recommendation} solved since recommended`
                    : 'Not practiced since recommended'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

export default RecentActivity