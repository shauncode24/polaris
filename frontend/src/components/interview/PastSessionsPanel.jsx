// frontend/src/components/interview/PastSessionsPanel.jsx
import './PastSessionsPanel.css'

function formatWhen(iso) {
  const date = new Date(iso)
  const today = new Date()
  const isToday = date.toDateString() === today.toDateString()
  if (isToday) return 'Today'
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function SessionCard({ session, active, onClick }) {
  const title = session.target_role || session.question
  return (
    <button
      type="button"
      className={`past-sessions__card ${active ? 'past-sessions__card--active' : ''}`}
      onClick={onClick}
    >
      <span className="past-sessions__title">{title}</span>
      {session.target_company && <span className="past-sessions__company">{session.target_company}</span>}
      <span className="past-sessions__date">{formatWhen(session.created_at)}</span>
    </button>
  )
}

function PastSessionsPanel({ sessions, loading, activeSessionId, onSelect }) {
  return (
    <section className="past-sessions">
      <h3>Past sessions</h3>
      <p className="past-sessions__lead">Review what you practiced</p>

      {loading ? (
        <p className="past-sessions__empty">Loading…</p>
      ) : sessions.length === 0 ? (
        <p className="past-sessions__empty">No sessions yet — your first practice round will show up here.</p>
      ) : (
        <div className="past-sessions__list">
          {sessions.slice(0, 3).map((s) => (
            <SessionCard
              key={s.session_id || s.id}
              session={s}
              active={(s.session_id || s.id) === activeSessionId}
              onClick={() => onSelect(s)}
            />
          ))}
        </div>
      )}

      {sessions.length > 3 && (
        <span className="past-sessions__see-all">See all session history</span>
      )}
    </section>
  )
}

export default PastSessionsPanel