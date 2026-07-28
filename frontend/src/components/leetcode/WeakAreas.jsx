// frontend/src/components/leetcode/WeakAreas.jsx
import './WeakAreas.css'

function WeakAreas({ topicMastery, longestGapDays }) {
  const weak = (topicMastery || [])
    .filter((t) => t.mastery === 'Not Practiced' || t.mastery === 'Introduced')
    .sort((a, b) => a.problems - b.problems)
    .slice(0, 4)

  if (weak.length === 0) {
    return (
      <section className="lc-card lc-weak">
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
          <div className="lc-weak__item" key={t.topic}>
            <div className="lc-weak__item-row">
              <span className="lc-weak__item-name">{t.topic}</span>
              <span className="lc-weak__item-count">{t.problems} solved</span>
            </div>
            <p className="lc-weak__item-detail">
              {t.problems === 0
                ? 'No problems solved in this topic yet.'
                : `Only ${t.problems} problem${t.problems === 1 ? '' : 's'} solved — mastery is still "${t.mastery}".`}
              {longestGapDays > 14 && ' Practice consistency has dropped recently.'}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}

export default WeakAreas