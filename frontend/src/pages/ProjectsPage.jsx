import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listProjects, getProjectsInsights } from '../api/projects'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import ProjectsHeader from '../components/projects/ProjectsHeader'
import ProjectsStatsGrid from '../components/projects/ProjectsStatsGrid'
import ProjectGallery from '../components/projects/ProjectGallery'
import ProjectIntelligencePanel from '../components/projects/ProjectIntelligencePanel'
import CompareProjectsPanel from '../components/projects/CompareProjectsPanel'
import AIRecommendationsPanel from '../components/projects/AIRecommendationsPanel'
import RecentMilestonesPanel from '../components/projects/RecentMilestonesPanel'
import SourceCoveragePanel from '../components/projects/SourceCoveragePanel'
import './ProjectsPage.css'

function ProjectsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview] = useState(null)
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')

  const loadAll = useCallback(async () => {
    setError('')
    try {
      const [overviewData, insightsData] = await Promise.all([
        listProjects(token),
        getProjectsInsights(token),
      ])
      setOverview(overviewData)
      setInsights(insightsData)
    } catch (err) {
      setError(err.message || 'Could not load your projects.')
    }
  }, [token])

  useEffect(() => {
    setLoading(true)
    loadAll().finally(() => setLoading(false))
  }, [loadAll])

  async function handleAnalyzeAll() {
    setAnalyzing(true)
    try {
      await loadAll()
    } finally {
      setAnalyzing(false)
    }
  }

  function handleOpenProject(project) {
    if (project.repo_url) {
      window.open(project.repo_url, '_blank', 'noopener,noreferrer')
    } else {
      navigate('/profile')
    }
  }

  const projects = overview?.projects || []
  const featuredProject = projects.find((p) => p.is_featured) || projects[0]

  return (
    <div className="projects-page">
      <Sidebar />
      <div className="projects-page__main">
        <BreadcrumbBar section="Projects" page="Overview" />

        <div className="projects-page__content">
          <ProjectsHeader onAnalyzeAll={handleAnalyzeAll} analyzing={analyzing} />

          {error && <p className="projects-page__error">{error}</p>}

          <ProjectsStatsGrid stats={overview?.stats} />

          <div className="projects-page__columns">
            <div className="projects-page__col projects-page__col--main">
              <ProjectGallery
                projects={projects}
                loading={loading}
                onOpenProject={handleOpenProject}
                onAddProject={() => navigate('/profile')}
              />

              {insights?.comparison && <CompareProjectsPanel comparison={insights.comparison} />}
              {insights?.recommendations?.length > 0 && (
                <AIRecommendationsPanel recommendations={insights.recommendations} />
              )}
            </div>

            <div className="projects-page__col projects-page__col--side">
              <ProjectIntelligencePanel featuredProjectName={featuredProject?.name} />
              <SourceCoveragePanel coverage={insights?.source_coverage} />
              <RecentMilestonesPanel milestones={insights?.milestones} />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProjectsPage