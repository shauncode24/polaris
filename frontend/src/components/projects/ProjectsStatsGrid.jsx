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