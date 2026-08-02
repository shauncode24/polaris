import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './PriorityFixes.css'

const VISIBLE_COUNT = 5

export default function PriorityFixes({ suggestions = [] }) {
  const [showAll, setShowAll] = useState(false)

  if (suggestions.length === 0) return null

  const visible = showAll ? suggestions : suggestions.slice(0, VISIBLE_COUNT)
  const hiddenCount = suggestions.length - VISIBLE_COUNT

  return (
    <CollapsibleSection
      title="Priority Fixes"
      subtitle={`${suggestions.length} recommendation${suggestions.length !== 1 ? 's' : ''}`}
      defaultOpen={true}
      className="pfix"
      dense
    >
      <div className="pfix__list">
        {visible.map((s, i) => (
          <div className="pfix__item" key={i}>
            <span className={`pfix__badge pfix__badge--${s.priority}`}>{s.priority}</span>
            <div className="pfix__content">
              <div className="pfix__title">{s.title}</div>
              <div className="pfix__detail">{s.detail}</div>
              {s.impact && <div className="pfix__impact">{s.impact}</div>}
            </div>
          </div>
        ))}
      </div>

      {hiddenCount > 0 && (
        <button type="button" className="pfix__toggle" onClick={() => setShowAll(v => !v)}>
          {showAll ? 'Show fewer ▲' : `View all ${suggestions.length} ▼`}
        </button>
      )}
    </CollapsibleSection>
  )
}