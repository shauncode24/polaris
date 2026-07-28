import './GroupedStatsBar.css'

function GroupedStatsBar({ totalSolved, activeDays, easy, medium, hard, contestRating }) {
  return (
    <div className="grouped-stats">
      <div className="grouped-stats__group">
        <span className="grouped-stats__label">Practice</span>
        <div className="grouped-stats__row">
          <div className="grouped-stats__item"><strong>{totalSolved ?? 0}</strong><span>solved</span></div>
          <div className="grouped-stats__item"><strong>{activeDays ?? 0}</strong><span>active days (30d)</span></div>
        </div>
      </div>
      <div className="grouped-stats__divider" />
      <div className="grouped-stats__group">
        <span className="grouped-stats__label">Difficulty</span>
        <div className="grouped-stats__row">
          <div className="grouped-stats__item grouped-stats__item--easy"><strong>{easy ?? 0}</strong><span>Easy</span></div>
          <div className="grouped-stats__item grouped-stats__item--medium"><strong>{medium ?? 0}</strong><span>Medium</span></div>
          <div className="grouped-stats__item grouped-stats__item--hard"><strong>{hard ?? 0}</strong><span>Hard</span></div>
        </div>
      </div>
      <div className="grouped-stats__divider" />
      <div className="grouped-stats__group">
        <span className="grouped-stats__label">Competitive</span>
        <div className="grouped-stats__row">
          <div className="grouped-stats__item">
            <strong>{contestRating != null ? Math.round(contestRating) : 'Unrated'}</strong>
            <span>contest rating</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default GroupedStatsBar