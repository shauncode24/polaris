import './Badge.css'

function Badge({ children, tone = 'live' }) {
  return (
    <span className={`badge badge--${tone}`}>
      <span className="badge__dot" />
      {children}
    </span>
  )
}

export default Badge
