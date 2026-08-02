import CollapsibleSection from '../common/CollapsibleSection'
import './RecentMilestonesPanel.css'

function formatMilestoneDate(iso) {
  if (!iso) return ''
  const date = new Date(iso)
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

// Doc: "Move to the bottom. Collapse by default. History is secondary
// information." Same `milestones` data (MilestoneItem[]) as before — now
// wrapped in CollapsibleSection (defaultOpen=false) instead of an always-
// expanded InfoCard.
function RecentMilestonesPanel({ milestones }) {
  return (
    <CollapsibleSection
      title="Recent activity"
      subtitle={milestones?.length ? `${milestones.length} recent event(s)` : 'No activity yet'}
      defaultOpen={false}
      dense
    >
      {!milestones || milestones.length === 0 ? (
        <p className="recent-milestones__empty">Sync your profile to start building a milestone history.</p>
      ) : (
        <ul className="recent-milestones__list">
          {milestones.map((m, i) => (
            <li key={i} className="recent-milestones__item">
              <span className="recent-milestones__label">{m.label}</span>
              {m.occurred_at && <span className="recent-milestones__date">{formatMilestoneDate(m.occurred_at)}</span>}
            </li>
          ))}
        </ul>
      )}
    </CollapsibleSection>
  )
}

export default RecentMilestonesPanel