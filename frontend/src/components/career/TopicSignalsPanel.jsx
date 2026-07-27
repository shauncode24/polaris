// frontend/src/components/career/TopicSignalsPanel.jsx
import './TopicSignalsPanel.css'

const GROUPS = [
  { key: 'strong', label: 'Strong', coverages: ['strong'], dot: 'strong' },
  { key: 'partial', label: 'Partial', coverages: ['partial'], dot: 'partial' },
  { key: 'weak', label: 'Weak / missing', coverages: ['weak', 'none'], dot: 'weak' },
  { key: 'unknown', label: 'Unclear', coverages: ['unknown'], dot: 'unknown' },
]

function TopicSignalsPanel({ topicSignals }) {
  if (!topicSignals || topicSignals.length === 0) return null

  const groupCounts = GROUPS.map((g) => ({
    ...g,
    items: topicSignals.filter((t) => g.coverages.includes(t.coverage)),
  })).filter((g) => g.items.length > 0)

  return (
    <section className="topic-signals">
      <h2>Where you stand</h2>
      <p className="topic-signals__lead">Coverage signals make the roadmap's priorities transparent.</p>

      <div className="topic-signals__rows">
        {groupCounts.map((group) => (
          <div key={group.key} className="topic-signals__row">
            <span className={`topic-signals__dot topic-signals__dot--${group.dot}`} />
            <span className="topic-signals__row-label">{group.label}</span>
            <span className="topic-signals__row-count">{group.items.length}</span>
            <div className="topic-signals__chips">
              {group.items.map((t) => (
                <span key={t.topic} className="topic-signals__chip" title={t.reasons?.join(' · ')}>
                  {t.topic} <span className="topic-signals__info">ⓘ</span>
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export default TopicSignalsPanel