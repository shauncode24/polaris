// frontend/src/components/leetcode/CareerInsights.jsx
// Grounded in the same blind_spots the backend computes (leetcode_insights.py)
// rather than fabricated per-company percentages, which the sync pipeline
// has no basis for producing.
import './CareerInsights.css'

function buildTracks(blindSpots, attendedContestsCount) {
  const missingFundamentals = blindSpots?.missing_fundamentals || []
  const advancedTopics = blindSpots?.advanced_topics || []

  const tracks = [
    {
      label: 'DSA Fundamentals',
      ready: missingFundamentals.length === 0,
      note: missingFundamentals.length === 0
        ? 'Ready'
        : `Needs: ${missingFundamentals.slice(0, 2).join(', ')}`,
    },
    {
      label: 'Advanced / SDE-2 style',
      ready: missingFundamentals.length === 0 && advancedTopics.length === 0,
      note: advancedTopics.length === 0
        ? (missingFundamentals.length === 0 ? 'Ready' : 'Close fundamentals first')
        : `Needs: ${advancedTopics.slice(0, 2).join(', ')}`,
    },
    {
      label: 'Competitive Programming',
      ready: (attendedContestsCount || 0) >= 5,
      note: (attendedContestsCount || 0) >= 5 ? 'Ready' : 'Not enough contest reps yet',
    },
  ]

  return tracks
}

function CareerInsights({ blindSpots, attendedContestsCount }) {
  const tracks = buildTracks(blindSpots, attendedContestsCount)

  return (
    <section className="lc-card lc-career">
      <h3>Career insights</h3>
      <div className="lc-career__list">
        {tracks.map((t) => (
          <div className="lc-career__item" key={t.label}>
            <span className="lc-career__label">{t.label}</span>
            <span className={`lc-career__note ${t.ready ? 'lc-career__note--ready' : 'lc-career__note--warn'}`}>
              {t.note}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

export default CareerInsights