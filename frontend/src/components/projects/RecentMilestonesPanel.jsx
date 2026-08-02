import InfoCard from '../common/InfoCard'
import { IconFlag } from '../icons/Icons'
import './RecentMilestonesPanel.css'

function formatMilestoneDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function RecentMilestonesPanel({ milestones }) {
  return (
    <InfoCard icon={IconFlag} iconTone="accent" title="Recent milestones">
      {!milestones || milestones.length === 0 ? (
        <p className="recent-milestones__empty">Sync your profile to start building a milestone history.</p>
      ) : (
        <ul className="recent-milestones__list">
          {milestones.map((m, i) => (
            <li key={i} className="recent-milestones__item">
              <span className="recent-milestones__label">{m.label}</span>
              {m.occurred_at && (
                <span className="recent-milestones__date">{formatMilestoneDate(m.occurred_at)}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </InfoCard>
  )
}

export default RecentMilestonesPanel