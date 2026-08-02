import Card from '../common/Card'
import './ProjectsStatsGrid.css'

function StatBlock({ value, label }) {
  return (
    <Card className="projects-stat">
      <span className="projects-stat__value">{value}</span>
      <span className="projects-stat__label">{label}</span>
    </Card>
  )
}

// Redesign note: cut from 8 KPIs to the 4 that matter for an at-a-glance
// summary (doc: "SUMMARY" section). The rest (capabilities, flagship count,
// claim risks, resume coverage) still exist in the data and now surface
// contextually — flagship/claim-risk inline on each ProjectRow, resume
// coverage inside Evidence Coverage — instead of competing for top-of-page
// attention.
function ProjectsStatsGrid({ stats }) {
  const items = [
    { value: stats?.total ?? 0, label: 'Projects' },
    { value: stats?.connected_repositories ?? 0, label: 'Connected Repos' },
    { value: stats?.technologies ?? 0, label: 'Technologies' },
    { value: `${stats?.github_coverage_pct ?? 0}%`, label: 'GitHub Coverage' },
  ]

  return (
    <div className="projects-stats-grid">
      {items.map((item) => (
        <StatBlock key={item.label} value={item.value} label={item.label} />
      ))}
    </div>
  )
}

export default ProjectsStatsGrid