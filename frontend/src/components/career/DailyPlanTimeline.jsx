import { useState } from 'react'
import './DailyPlanTimeline.css'

function DayCard({ item, expanded, onToggle, isToday }) {
  return (
    <li className={`day-card ${isToday ? 'day-card--today' : ''}`}>
      <button type="button" className="day-card__header" onClick={onToggle}>
        <span className="day-card__day">Day {item.day}</span>
        <span className="day-card__theme">{item.theme}</span>
        {item.day_type && <span className="day-card__type">{item.day_type}</span>}
        <span className="day-card__chevron">{expanded ? '−' : '+'}</span>
      </button>
      {expanded && (
        <div className="day-card__body">
          {item.tasks?.length > 0 && (
            <ul className="day-card__tasks">
              {item.tasks.map((t, i) => <li key={i}>{t}</li>)}
            </ul>
          )}
          <div className="day-card__meta">
            {item.estimated_time && <span>⏱ {item.estimated_time}</span>}
            {item.deliverable && <span>✓ {item.deliverable}</span>}
          </div>
          {item.rationale && <p className="day-card__rationale">{item.rationale}</p>}
          {item.source === 'fallback' && (
            <p className="day-card__fallback-note">Auto-filled after the plan generator couldn't reach this day.</p>
          )}
        </div>
      )}
    </li>
  )
}

function DailyPlanTimeline({ dailyPlan, checkIns, daysAvailable }) {
  const [expandedDay, setExpandedDay] = useState(dailyPlan?.[0]?.day ?? null)

  if (!dailyPlan || dailyPlan.length === 0) return null

  const today = dailyPlan[0]

  return (
    <section className="daily-plan">
      <div className="daily-plan__today">
        <h2>Today's Focus</h2>
        <p className="daily-plan__today-theme">{today.theme}</p>
        {today.tasks?.length > 0 && (
          <ul className="daily-plan__today-tasks">
            {today.tasks.map((t, i) => <li key={i}>{t}</li>)}
          </ul>
        )}
        <div className="daily-plan__today-meta">
          {today.estimated_time && <span>⏱ {today.estimated_time}</span>}
          {today.deliverable && <span>✓ {today.deliverable}</span>}
        </div>
      </div>

      <h2 className="daily-plan__heading">Full Roadmap ({daysAvailable} day{daysAvailable === 1 ? '' : 's'})</h2>
      <ul className="daily-plan__list">
        {dailyPlan.map((item) => (
          <DayCard
            key={item.day}
            item={item}
            isToday={item.day === today.day}
            expanded={expandedDay === item.day}
            onToggle={() => setExpandedDay(expandedDay === item.day ? null : item.day)}
          />
        ))}
      </ul>

      {checkIns?.length > 0 && (
        <div className="daily-plan__checkins">
          <h3>Milestone Check-ins</h3>
          <ul>
            {checkIns.map((c, i) => <li key={i}>{c}</li>)}
          </ul>
        </div>
      )}
    </section>
  )
}

export default DailyPlanTimeline