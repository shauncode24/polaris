// frontend/src/components/leetcode/WeakAreas.jsx
// Redesigned as a compact quick-action panel (Review §"Weak Areas") —
// status + Practice link only, no repeated explanatory paragraphs.
import './WeakAreas.css'

function slugFor(topic) {
  return topic.toLowerCase().replace(/[^a-z0-9]+/g, '-')
}

function WeakAreas({ topicMastery }) {
  const weak = (topicMastery || [])
    .filter((t) => t.mastery === 'Not Practiced' || t.mastery === 'Introduced')
    .sort((a, b) => a.problems - b.problems)
    .slice(0, 5)

  if (weak.length === 0) {
    return (
      <section className="lc-card">
        <h3>Weak areas</h3>
        <p className="lc-empty-text">No clear weak areas detected — nice, broad coverage.</p>
      </section>
    )
  }

  return (
    <section className="lc-card lc-weak">
      <h3>Weak areas</h3>
      <div className="lc-weak__list">
        {weak.map((t) => (
          <div className="lc-weak__row" key={t.topic}>
            <div className="lc-weak__row-text">
              <span className="lc-weak__item-name">{t.topic}</span>
              <span className="lc-weak__item-count">
                {t.problems === 0 ? 'Never practiced' : `${t.problems} solved · ${t.mastery}`}
              </span>
            </div>
            <a
              className="lc-weak__practice-btn"
              href={`https://leetcode.com/tag/${slugFor(t.topic)}/`}
              target="_blank"
              rel="noreferrer"
            >
              Practice →
            </a>
          </div>
        ))}
      </div>
    </section>
  )
}

export default WeakAreas