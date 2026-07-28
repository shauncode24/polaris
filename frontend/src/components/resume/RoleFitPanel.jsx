import CollapsibleSection from '../common/CollapsibleSection'
import './RoleFitPanel.css'

function pctClass(pct) {
  if (pct == null) return ''
  if (pct >= 70) return 'rfp__pct--high'
  if (pct >= 40) return 'rfp__pct--mid'
  return 'rfp__pct--low'
}

export default function RoleFitPanel({ role_fit = [] }) {
  return (
    <CollapsibleSection title="Compatible Roles" defaultOpen={false} className="rfp">
      <div className="rfp__body">
        {role_fit.length === 0 ? (
          <div className="rfp__empty">
            Add skills to your profile to see compatible roles.
          </div>
        ) : (
          role_fit.map((fit) => (
            <div className="rfp__item" key={fit.role}>
              <div className="rfp__info">
                <div className="rfp__role">{fit.role}</div>
              </div>
              <div className={`rfp__pct ${pctClass(fit.match_pct)}`}>
                {fit.match_pct != null ? `${fit.match_pct}%` : '—'}
              </div>
            </div>
          ))
        )}
      </div>
    </CollapsibleSection>
  )
}
