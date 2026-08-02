import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeEvolution.css'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function ResumeEvolution({ evolution }) {
  const [expanded, setExpanded] = useState(false)

  if (!evolution || !evolution.has_previous) return null

  const {
    previous_snapshot_at,
    current_snapshot_at,
    skills_gained = [],
    skills_lost = [],
    skills_strengthened = [],
    skills_weakened = [],
    summary,
  } = evolution

  return (
    <CollapsibleSection title="Resume Evolution" defaultOpen={false} className="revo">
      <div className="revo__body">
        <div className="revo__compact-row">
          {skills_gained.length > 0 && <span className="revo__compact-chip revo__compact-chip--up">+{skills_gained.length} Skills</span>}
          {skills_strengthened.length > 0 && <span className="revo__compact-chip revo__compact-chip--up">+{skills_strengthened.length} Strengthened</span>}
          {skills_lost.length > 0 && <span className="revo__compact-chip revo__compact-chip--down">-{skills_lost.length} Skills</span>}
          {skills_weakened.length > 0 && <span className="revo__compact-chip revo__compact-chip--down">{skills_weakened.length} Weakened</span>}
          <button type="button" className="revo__timeline-btn" onClick={() => setExpanded(v => !v)}>
            {expanded ? 'Hide Timeline' : 'View Timeline'}
          </button>
        </div>

        {expanded && (
          <>
            {summary && <div className="revo__summary">{summary}</div>}

            {previous_snapshot_at && current_snapshot_at && (
              <div className="revo__meta">
                {formatDate(previous_snapshot_at)} → {formatDate(current_snapshot_at)}
              </div>
            )}

            {skills_gained.length > 0 && (
              <div>
                <div className="revo__section-label">Skills Gained</div>
                <div className="revo__chips">
                  {skills_gained.map((s) => <span key={s} className="revo__chip revo__chip--gained">{s}</span>)}
                </div>
              </div>
            )}

            {skills_lost.length > 0 && (
              <div>
                <div className="revo__section-label">Skills Lost</div>
                <div className="revo__chips">
                  {skills_lost.map((s) => <span key={s} className="revo__chip revo__chip--lost">{s}</span>)}
                </div>
              </div>
            )}

            {skills_strengthened.length > 0 && (
              <div>
                <div className="revo__section-label">Strengthened</div>
                <div className="revo__delta-list">
                  {skills_strengthened.slice(0, 5).map((d) => (
                    <div key={d.skill} className="revo__delta-row">
                      <span className="revo__delta-skill">{d.skill}</span>
                      <span className="revo__delta-val revo__delta-val--up">+{Math.round(d.delta * 100)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {skills_weakened.length > 0 && (
              <div>
                <div className="revo__section-label">Weakened</div>
                <div className="revo__delta-list">
                  {skills_weakened.slice(0, 5).map((d) => (
                    <div key={d.skill} className="revo__delta-row">
                      <span className="revo__delta-skill">{d.skill}</span>
                      <span className="revo__delta-val revo__delta-val--down">{Math.round(d.delta * 100)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </CollapsibleSection>
  )
}