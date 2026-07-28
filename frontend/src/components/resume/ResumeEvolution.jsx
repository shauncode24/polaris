import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeEvolution.css'

function formatDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function ResumeEvolution({ evolution }) {
  if (!evolution) return null

  const {
    has_previous,
    previous_snapshot_at,
    current_snapshot_at,
    skills_gained = [],
    skills_lost = [],
    skills_strengthened = [],
    skills_weakened = [],
    summary,
  } = evolution

  const badge = (skills_gained.length + skills_lost.length + skills_strengthened.length + skills_weakened.length) > 0
    ? <span className="csec__badge" style={{ background: 'var(--accent-soft)', color: 'var(--accent)', border: 'none', fontSize: 11, padding: '2px 7px', borderRadius: '999px', fontWeight: 700 }}>Updated</span>
    : null

  return (
    <CollapsibleSection title="Resume Evolution" defaultOpen={false} className="revo" badge={badge}>
      <div className="revo__body">
        {summary && <div className="revo__summary">{summary}</div>}

        {!has_previous && (
          <div className="revo__empty">
            Upload a second resume version to see how your skills have evolved.
          </div>
        )}

        {has_previous && (
          <>
            {previous_snapshot_at && current_snapshot_at && (
              <div className="revo__meta">
                {formatDate(previous_snapshot_at)} → {formatDate(current_snapshot_at)}
              </div>
            )}

            {skills_gained.length > 0 && (
              <div>
                <div className="revo__section-label">Skills Gained</div>
                <div className="revo__chips">
                  {skills_gained.map((s) => (
                    <span key={s} className="revo__chip revo__chip--gained">{s}</span>
                  ))}
                </div>
              </div>
            )}

            {skills_lost.length > 0 && (
              <div>
                <div className="revo__section-label">Skills Lost</div>
                <div className="revo__chips">
                  {skills_lost.map((s) => (
                    <span key={s} className="revo__chip revo__chip--lost">{s}</span>
                  ))}
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
