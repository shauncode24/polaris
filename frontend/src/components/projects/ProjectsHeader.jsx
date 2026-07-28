import { useNavigate } from 'react-router-dom'
import Button from '../common/Button'
import { IconGithub } from '../icons/Icons'
import { IconSparkle } from '../icons/DashboardIcons'
import './ProjectsHeader.css'

function ProjectsHeader({ onAnalyzeAll, analyzing }) {
  const navigate = useNavigate()

  return (
    <div className="projects-header">
      <div>
        <h1 className="projects-header__title">Projects</h1>
        <p className="projects-header__sub">
          What you built — and what each project proves about your engineering ability.
        </p>
      </div>
      <div className="projects-header__actions">
        <Button variant="outline" size="sm" icon={<IconGithub size={16} />} onClick={() => navigate('/build-profile')}>
          Import from GitHub
        </Button>
        <Button variant="outline" size="sm" icon={<IconSparkle size={16} />} onClick={onAnalyzeAll} disabled={analyzing}>
          {analyzing ? 'Analyzing…' : 'Analyze all'}
        </Button>
        <Button variant="primary" size="sm" onClick={() => navigate('/profile')}>
          + New project
        </Button>
      </div>
    </div>
  )
}

export default ProjectsHeader