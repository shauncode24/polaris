// frontend/src/components/career/MilestoneCheckins.jsx
import './MilestoneCheckins.css'

function parseCheckIn(text, index, total) {
  // "Day 3 check-in" / "Final review day before the interview/deadline"
  const match = text.match(/^Day (\d+) check-in$/i)
  if (match) {
    return { label: `Day ${match[1]}`, title: 'Progress check-in', sub: 'A quick pulse check on the plan so far.' }
  }
  return { label: `Day ${total}`, title: 'Final review', sub: text }
}

function MilestoneCheckins({ checkIns, daysAvailable }) {
  if (!checkIns || checkIns.length === 0) return null

  return (
    <section className="milestones">
      <h3>Milestone check-ins</h3>
      <div className="milestones__grid">
        {checkIns.map((c, i) => {
          const parsed = parseCheckIn(c, i, daysAvailable)
          return (
            <div className="milestones__item" key={i}>
              <span className="milestones__label">{parsed.label} · {parsed.title}</span>
              <span className="milestones__sub">{parsed.sub}</span>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default MilestoneCheckins