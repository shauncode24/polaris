import './TopicSignalsPanel.css'

const GROUPS = [
  { key: 'strong', label: 'Strong', coverages: ['strong'] },
  { key: 'partial', label: 'Partial', coverages: ['partial'] },
  { key: 'weak', label: 'Weak / Missing', coverages: ['weak', 'none'] },
  { key: 'unknown', label: 'Unclear', coverages: ['unknown'] },
]

function TopicSignalsPanel({ topicSignals }) {
  if (!topicSignals || topicSignals.length === 0) return null

  return (
    <section className="topic-signals">
      <h2>Where You Stand</h2>
      <p className="topic-signals__lead">
        Best-effort coverage for this goal's curriculum, based on your verified skills, projects, and LeetCode history.
      </p>
      <div className="topic-signals__groups">
        {GROUPS.map((group) => {
          const items = topicSignals.filter((t) => group.coverages.includes(t.coverage))
          if (items.length === 0) return null
          return (
            <div key={group.key} className={`topic-signals__group topic-signals__group--${group.key}`}>
              <h3>{group.label} <span>{items.length}</span></h3>
              <ul>
                {items.map((t) => (
                  <li key={t.topic} title={t.reasons?.join(' · ')}>
                    {t.topic}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default TopicSignalsPanel