import Card from '../common/Card'
import { IconFolder } from '../icons/DashboardIcons'
import './ProjectIntelligenceCard.css'

function ProjectIntelligenceCard({ projects }) {
  const hasProjects = projects && projects.length > 0

  return (
    <Card className="project-intel">
      <div className="project-intel__header">
        <div>
          <h3>Project intelligence</h3>
          <p>Build interview-ready ways to explain your work.</p>
        </div>
        <a className="project-intel__link" href="#projects">Open projects →</a>
      </div>

      {hasProjects ? (
        <div className="project-intel__grid">
          {projects.map((p) => (
            <div className="project-intel__tile" key={p.name}>
              <span className="project-intel__tile-name">{p.name}</span>
              <span className="project-intel__tile-desc">{p.description}</span>
              <button type="button" className="project-intel__tile-cta">Explain like I'm interviewing →</button>
            </div>
          ))}
        </div>
      ) : (
        <div className="project-intel__empty">
          <IconFolder size={20} />
          <p>Sync GitHub or add projects to your resume to unlock project intelligence.</p>
        </div>
      )}
    </Card>
  )
}

export default ProjectIntelligenceCard