import InfoCard from '../common/InfoCard'
import { IconFlag } from '../icons/Icons'
import './RecentMilestonesPanel.css'

function RecentMilestonesPanel({ milestones }) {
  return (
    <InfoCard icon={IconFlag} iconTone="accent" title="Recent milestones">
      {!milestones || milestones.length === 0 ? (
        <p className="recent-milestones__empty">Sync your profile to start building a milestone history.</p>
      ) : (
        <ul className="recent-milestones__list">
          {milestones.map((m, i) => (
            <li key={i}>{m.label}</li>
          ))}
        </ul>
      )}
    </InfoCard>
  )
}

export default RecentMilestonesPanel