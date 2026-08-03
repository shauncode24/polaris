// frontend/src/components/leetcode/TopicBreakdown.jsx
// Evidence Generated is now merged in here (Review §"What Should Be
// Merged") — each row already carries mastery + count, so a separate
// evidence grid duplicated the same information.
import { useState } from 'react'
import { confidenceTier, tierDisplayLabel, confidenceLabel } from '../../utils/leetcodeMastery'
import { supportsFor } from '../../utils/topicSupports'
import './TopicBreakdown.css'

function TopicRow({ topic, maxProblems }) {
  const [expanded, setExpanded] = useState(false)
  const tier = confidenceTier(topic.mastery)
  const pct = maxProblems > 0 ? Math.max(4, Math.round((topic.problems / maxProblems) * 100)) : 0
  const isWeighted = typeof topic.weighted_score === 'number' && topic.weighted_score !== topic.problems
  const supports = supportsFor(topic.topic)

  function handleAddToResume() {
    alert(`Add "${topic.topic}" evidence to your resume! Resume text editor coming soon.`)
  }

  return (
    <li className="lc-topic">
      <button type="button" className="lc-topic__row" onClick={() => setExpanded((v) => !v)}>
        <span className="lc-topic__name">{topic.topic}</span>
        <span className="lc-topic__track">
          <span className={`lc-topic__fill lc-topic__fill--${tier}`} style={{ width: `${pct}%` }} />
        </span>
        <span className="lc-topic__count">{topic.problems}</span>
        <span className={`lc-topic__badge lc-topic__badge--${tier}`}>{tierDisplayLabel(tier)}</span>
        <span className="lc-topic__chevron">{expanded ? '⌄' : '›'}</span>
      </button>
      {expanded && (
        <div className="lc-topic__detail">
          <p>
            Mastery level: <strong>{topic.mastery}</strong> — {topic.problems} problem{topic.problems === 1 ? '' : 's'} solved
            {isWeighted && <> (difficulty-weighted score: {topic.weighted_score})</>}.
            {topic.problems > 0 && <> {confidenceLabel(tier)} confidence for interview evidence.</>}
          </p>
          {topic.problems > 0 && (
            <>
              {supports.length > 0 && (
                <div className="lc-topic__supports">
                  {supports.map((s) => <span key={s} className="lc-topic__support-tag">{s}</span>)}
                </div>
              )}
              <button type="button" className="lc-topic__add-btn" onClick={handleAddToResume}>
                + Add to resume
              </button>
            </>
          )}
        </div>
      )}
    </li>
  )
}

function TopicBreakdown({ topicMastery }) {
  const practiced = (topicMastery || []).filter((t) => t.problems > 0)
  const untouched = (topicMastery || []).filter((t) => t.problems === 0)
  const maxProblems = practiced.reduce((m, t) => Math.max(m, t.problems), 0)
  const ordered = [...practiced.sort((a, b) => b.problems - a.problems), ...untouched]

  return (
    <section className="lc-card">
      <h2>Topic breakdown</h2>
      <p className="lc-card__lead">The patterns your problem-solving history can genuinely support — expand a topic to add it as resume evidence.</p>

      {ordered.length === 0 ? (
        <p className="lc-empty-text">No topics practiced yet — sync your account to populate this.</p>
      ) : (
        <ul className="lc-topic__list">
          {ordered.map((t) => (
            <TopicRow key={t.topic} topic={t} maxProblems={maxProblems} />
          ))}
        </ul>
      )}
    </section>
  )
}

export default TopicBreakdown