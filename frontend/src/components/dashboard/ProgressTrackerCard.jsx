import { useNavigate } from 'react-router-dom'
import InfoCard from '../common/InfoCard'
import { IconChartBar } from '../icons/DashboardIcons'
import './ProgressTrackerCard.css'

// TODO: replace with real deltas from GET /profile-snapshots once that
// endpoint exists (Phase 9 of the design doc). Bars below are visual
// placeholders only — no numbers are displayed/claimed, matching the
// screenshot's "not enough history yet" state.
const PLACEHOLDER_BARS = [38, 52, 30, 68, 44, 74]

function ProgressTrackerCard() {
  const navigate = useNavigate()

  return (
    <InfoCard icon={IconChartBar} iconTone="accent" title="Progress tracker">
      <p className="progress-tracker__hint">Source deltas and confidence over time</p>
      <div className="progress-tracker__chart">
        {PLACEHOLDER_BARS.map((h, i) => (
          <div key={i} className="progress-tracker__bar" style={{ height: `${h}%` }} />
        ))}
      </div>
      <p className="progress-tracker__note">Sync again in a few days to see meaningful progress deltas.</p>
      <button type="button" className="progress-tracker__link" onClick={() => navigate('/build-profile')}>
        View full snapshot history →
      </button>
    </InfoCard>
  )
}

export default ProgressTrackerCard