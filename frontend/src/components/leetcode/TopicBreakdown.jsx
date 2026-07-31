// frontend/src/components/leetcode/TopicBreakdown.jsx
import { useState } from 'react'
import { confidenceTier, tierDisplayLabel } from '../../utils/leetcodeMastery'
import './TopicBreakdown.css'

function TopicRow({ topic, maxProblems }) {
  const [expanded, setExpanded] = useState(false)
  const tier = confidenceTier(topic.mastery)
  const pct = maxProblems > 0 ? Math.max(4, Math.round((topic.problems / maxProblems) * 100)) : 0
  const isWeighted = typeof topic.weighted_score === 'number' && topic.weighted_score !== topic.problems

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
          Mastery level: <strong>{topic.mastery}</strong> — {topic.problems} problem{topic.problems === 1 ? '' : 's'} solved in this topic
          {isWeighted && <> (difficulty-weighted score: {topic.weighted_score}, based on LeetCode's own fundamental/intermediate/advanced tag tiers)</>}.
        </div>
      )}
    </li>
  )
}

function TopicBreakdown({ topicMastery }) {
  const practiced = (topicMastery || []).filter((t) => t.problems > 0)
  const maxProblems = practiced.reduce((m, t) => Math.max(m, t.problems), 0)

  return (
    <section className="lc-card">
      <h2>Topic breakdown</h2>
      <p className="lc-card__lead">The patterns your problem-solving history can genuinely support.</p>

      {practiced.length === 0 ? (
        <p className="lc-empty-text">No topics practiced yet — sync your account to populate this.</p>
      ) : (
        <ul className="lc-topic__list">
          {practiced
            .sort((a, b) => b.problems - a.problems)
            .map((t) => (
              <TopicRow key={t.topic} topic={t} maxProblems={maxProblems} />
            ))}
        </ul>
      )}
    </section>
  )
}

export default TopicBreakdown