import { useNavigate } from 'react-router-dom'
import InfoCard from '../common/InfoCard'
import { IconChartBar } from '../icons/DashboardIcons'
import './ProgressTrackerCard.css'

// Phase 1 fix (§1.3 "No fake intelligence"): this card previously
// rendered PLACEHOLDER_BARS — six hardcoded bar heights, styled
// identically to a real chart, with no visual indication to the user
// that they weren't looking at real data. No GET /profile-snapshots-
// style history endpoint exists yet to back a real chart, so per the
// "become real or disappear" rule, the fake chart is removed rather
// than kept dressed up as real. Replace this with an actual rendered
// chart once a real history endpoint exists.
function ProgressTrackerCard() {
  const navigate = useNavigate()

  return (
    <InfoCard icon={IconChartBar} iconTone="accent" title="Progress tracker">
      <p className="progress-tracker__hint">Source deltas and confidence over time</p>
      <p className="progress-tracker__note">
        Not enough synced history yet to chart real progress. Sync your sources again in a few
        days once you have a baseline to compare against.
      </p>
      <button type="button" className="progress-tracker__link" onClick={() => navigate('/build-profile')}>
        View full snapshot history →
      </button>
    </InfoCard>
  )
}

export default ProgressTrackerCard