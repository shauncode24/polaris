import { useNavigate } from 'react-router-dom'
import InfoCard from '../common/InfoCard'
import { IconBell } from '../icons/DashboardIcons'
import './NudgesCard.css'

// TODO: no /nudges endpoint exists yet (design doc §7.1 is explicitly V2
// scope, rule-based, event-driven). This one static nudge mirrors the
// only rule that's realistically always true pre-goal, so it's not a
// fabricated claim — it's structurally correct even without the engine.
function NudgesCard() {
  const navigate = useNavigate()

  return (
    <InfoCard
      icon={IconBell}
      title="Nudges"
      badge={<span className="nudges-card__count">1</span>}
    >
      <div className="nudges-card__item">
        <p className="nudges-card__item-title">Set a goal to unlock your roadmap</p>
        <p className="nudges-card__item-body">Polaris needs a target to focus your recommendations.</p>
        <button type="button" className="nudges-card__item-cta" onClick={() => navigate('/career-planner')}>
          Set a goal
        </button>
      </div>
    </InfoCard>
  )
}

export default NudgesCard