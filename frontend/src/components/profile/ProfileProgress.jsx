import './ProfileIngestion.css'

function ProfileProgress({ steps }) {
  const completed = steps.filter((s) => s.done).length
  const pct = steps.length ? Math.round((completed / steps.length) * 100) : 0

  return (
    <div className="profile-progress">
      <div className="profile-progress__bar">
        <div className="profile-progress__fill" style={{ width: `${pct}%` }} />
      </div>
      <ul className="profile-progress__steps">
        {steps.map((s) => (
          <li key={s.label} className={s.done ? 'is-done' : ''}>
            <span className="profile-progress__dot" />
            {s.label}
          </li>
        ))}
      </ul>
      <span className="profile-progress__pct">{pct}%</span>
    </div>
  )
}

export default ProfileProgress