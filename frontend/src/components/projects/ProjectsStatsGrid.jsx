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
    { value: stats?.flagship ?? 0, label: 'Flagship Projects' },
    { value: stats?.technologies ?? 0, label: 'Technologies' },
    { value: stats?.capabilities ?? 0, label: 'Capabilities' },
    { value: stats?.connected_repositories ?? 0, label: 'Connected Repos' },
    { value: stats?.claim_risk_count ?? 0, label: 'Claim Risks' },
    { value: `${stats?.resume_coverage_pct ?? 0}%`, label: 'Resume Coverage' },
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