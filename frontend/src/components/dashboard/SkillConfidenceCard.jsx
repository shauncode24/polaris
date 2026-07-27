import { useMemo, useState } from 'react'
import InfoCard from '../common/InfoCard'
import { IconTarget } from '../icons/Icons'
import './SkillConfidenceCard.css'

const LEVEL_TONE = { High: 'high', Medium: 'medium', Low: 'low' }

function levelFor(confidence) {
  if (confidence >= 0.6) return 'High'
  if (confidence >= 0.3) return 'Medium'
  return 'Low'
}

// TODO: replace with a real endpoint (e.g. GET /skills/confidence-summary)
// that aggregates skill_evidence by category server-side. For now this
// derives a per-category rollup from whatever the resume ingestion result
// already gave the client, so the bars are at least real for "by category"
// once wired — the raw category buckets below are placeholders matching
// the categories used in skill_categories.py.
const FALLBACK_CATEGORIES = [
  { category: 'Frontend', confidence: 0.78 },
  { category: 'Backend', confidence: 0.74 },
  { category: 'Cloud', confidence: 0.52 },
  { category: 'Data', confidence: 0.28 },
  { category: 'Systems', confidence: 0.27 },
  { category: 'Product', confidence: 0.5 },
]

function SkillConfidenceCard() {
  const [view, setView] = useState('category')
  const rows = useMemo(
    () => FALLBACK_CATEGORIES.map((c) => ({ ...c, level: levelFor(c.confidence) })),
    []
  )

  return (
    <InfoCard
      icon={IconTarget}
      iconTone="accent"
      title="Skill confidence"
      action={
        <div className="skill-confidence__toggle">
          <button type="button" className={view === 'category' ? 'is-active' : ''} onClick={() => setView('category')}>By category</button>
          <button type="button" className={view === 'skill' ? 'is-active' : ''} onClick={() => setView('skill')}>By skill</button>
        </div>
      }
    >
      <p className="skill-confidence__hint">Click a skill to see the evidence behind it.</p>
      <div className="skill-confidence__rows">
        {rows.map((row) => (
          <div className="skill-confidence__row" key={row.category}>
            <span className="skill-confidence__row-label">{row.category}</span>
            <div className="skill-confidence__bar">
              <div className={`skill-confidence__bar-fill skill-confidence__bar-fill--${LEVEL_TONE[row.level]}`} style={{ width: `${Math.round(row.confidence * 100)}%` }} />
            </div>
            <span className="skill-confidence__row-level">{row.level}</span>
          </div>
        ))}
      </div>
    </InfoCard>
  )
}

export default SkillConfidenceCard