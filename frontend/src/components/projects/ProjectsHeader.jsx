// frontend/src/components/projects/ProjectsHeader.jsx
import { useNavigate } from 'react-router-dom'
import Button from '../common/Button'
import { IconGithub } from '../icons/Icons'
import { IconSparkle } from '../icons/DashboardIcons'
import './ProjectsHeader.css'

export default function ProjectsHeader({
  onAnalyzeAll,
  analyzing,
  projectCount,
  interviewReadyCount,
}) {
  const navigate = useNavigate()

  return (
    <div className="projects-header">
      <div className="projects-header__left">
        <div className="projects-header__meta" style={{ paddingLeft: 0 }}>
          <div className="projects-header__title-row">
            <span className="projects-header__portfolio-title">Project Portfolio</span>
          </div>
        </div>

        {projectCount != null && (
          <>
            <div className="projects-header__divider" />
            <div className="projects-header__stats-strip">
              <div className="projects-header__stat-item projects-header__stat-item--primary">
                <span className="projects-header__stat-val">{projectCount}</span>
                <span className="projects-header__stat-lbl">TOTAL PROJECTS</span>
              </div>
              {interviewReadyCount != null && (
                <div className="projects-header__stat-item">
                  <span className="projects-header__stat-val">{interviewReadyCount}</span>
                  <span className="projects-header__stat-lbl">INTERVIEW READY</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="projects-header__right">
        <button
          type="button"
          className="projects-header__btn"
          onClick={() => navigate('/build-profile')}
        >
          <IconGithub size={13} />
          Import from GitHub
        </button>
        <button
          type="button"
          className="projects-header__btn projects-header__btn--primary"
          onClick={() => navigate('/profile')}
        >
          + New project
        </button>
        <button
          type="button"
          className="projects-header__btn projects-header__btn--primary"
          onClick={onAnalyzeAll}
          disabled={analyzing}
        >
          {analyzing ? (
            <>
              <span style={{ width: 12, height: 12, border: '2px solid rgba(255,255,255,0.4)', borderTopColor: '#fff', borderRadius: '50%', display: 'inline-block', animation: 'spin 0.7s linear infinite', marginRight: 4 }} />
              Analyzing…
            </>
          ) : (
            <>
              <IconSparkle size={13} style={{ marginRight: 4 }} />
              Analyze all
            </>
          )}
        </button>
      </div>
    </div>
  )
}