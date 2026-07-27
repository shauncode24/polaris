import { useState } from 'react'
import Card from '../common/Card'
import { IconSparkle } from '../icons/DashboardIcons'
import { IconArrowRight } from '../icons/Icons'
import './DecisionEngineCard.css'

// No backend endpoint exists for this yet (design doc's Layer 5 Decision
// Engine is V2 scope). UI is wired up and ready — swap the button's
// onClick for a real POST /decision-engine/plan call once it exists.
const TIME_OPTIONS = ['30 min', '1 hour', '2 hours']

function DecisionEngineCard() {
  const [selected, setSelected] = useState('1 hour')

  return (
    <Card className="decision-card">
      <div className="decision-card__header">
        <span className="decision-card__icon"><IconSparkle size={16} /></span>
        <div className="decision-card__title-group">
          <h3>Decision Engine</h3>
          <p>A focused session, composed for today</p>
        </div>
        <span className="decision-card__badge">Preview</span>
      </div>

      <p className="decision-card__copy">
        Tell Polaris how much time you have. It will combine your plan, progress, and nudges into one sensible next session.
      </p>

      <div className="decision-card__options">
        {TIME_OPTIONS.map((opt) => (
          <button
            key={opt}
            type="button"
            className={`decision-card__option ${selected === opt ? 'is-active' : ''}`}
            onClick={() => setSelected(opt)}
          >
            {opt}
          </button>
        ))}
      </div>

      <button type="button" className="decision-card__cta">
        Plan my time <IconArrowRight size={14} />
      </button>
    </Card>
  )
}

export default DecisionEngineCard