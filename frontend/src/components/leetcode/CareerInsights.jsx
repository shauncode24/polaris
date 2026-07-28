// frontend/src/components/leetcode/CareerInsights.jsx
// Deterministic readiness percentages (see utils/interviewReadiness.js) —
// this is the "Interview Readiness" feature: a weighted average over real
// topic_mastery data, never a fabricated per-company number.
import { computeReadinessTracks } from '../../utils/interviewReadiness'
import './CareerInsights.css'

function barTone(pct) {
  if (pct >= 70) return 'strong'
  if (pct >= 40) return 'partial'
  return 'weak'
}

function CareerInsights({ topicMastery, attendedContestsCount }) {
  const tracks = computeReadinessTracks(topicMastery)
  const contestReady = (attendedContestsCount || 0) >= 5

  return (
    <section className="lc-card lc-career">
      <h3>Interview readiness</h3>
      <p className="lc-card__lead">A weighted read of your topic mastery against what each interview style actually tests.</p>

      <div className="lc-career__list">
        {tracks.map((t) => (
          <div className="lc-career__row" key={t.key}>
            <div className="lc-career__row-top">
              <span className="lc-career__label">{t.label}</span>
              <span className="lc-career__pct">{t.percentage}%</span>
            </div>
            <div className="lc-career__track">
              <div className={`lc-career__fill lc-career__fill--${barTone(t.percentage)}`} style={{ width: `${t.percentage}%` }} />
            </div>
            {t.weakTopics.length > 0 && (
              <span className="lc-career__gap">Weakest: {t.weakTopics.slice(0, 2).join(', ')}</span>
            )}
          </div>
        ))}

        <div className="lc-career__row">
          <div className="lc-career__row-top">
            <span className="lc-career__label">Competitive Programming</span>
            <span className="lc-career__pct">{contestReady ? 'Ready' : 'Building'}</span>
          </div>
          <span className="lc-career__gap">
            {contestReady ? `${attendedContestsCount} contests attended` : 'Fewer than 5 rated contests attended so far'}
          </span>
        </div>
      </div>
    </section>
  )
}

export default CareerInsights