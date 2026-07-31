import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listProjects, getProjectsInsights } from '../api/projects'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import CollapsibleSection from '../components/common/CollapsibleSection'
import ProjectsHeader from '../components/projects/ProjectsHeader'
import ProjectsStatsGrid from '../components/projects/ProjectsStatsGrid'
import ProjectGallery from '../components/projects/ProjectGallery'
import InterviewToolkitPanel from '../components/projects/InterviewToolkitPanel'
import CompareProjectsPanel from '../components/projects/CompareProjectsPanel'
import AIRecommendationsPanel from '../components/projects/AIRecommendationsPanel'
import RecentMilestonesPanel from '../components/projects/RecentMilestonesPanel'
import EvidenceCoveragePanel from '../components/projects/EvidenceCoveragePanel'
import GoalAwareRankingPanel from '../components/projects/GoalAwareRankingPanel'
import PortfolioNarrativePanel from '../components/projects/PortfolioNarrativePanel'
import ProjectDetailModal from '../components/projects/ProjectDetailModal'
import './ProjectsPage.css'

function ProjectsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview] = useState(null)
  const [insights, setInsights] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [detailProject, setDetailProject] = useState(null)

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
  const featuredProject = projects.find((p) => p.tier === 'Flagship Project') || projects[0]
  const interviewReadyCount = projects.filter(
    (p) => p.tier === 'Flagship Project' || p.tier === 'Career Project'
  ).length

  return (
    <div className="projects-page">
      <Sidebar />
      <div className="projects-page__main">
        <BreadcrumbBar section="Projects" page="Overview" />

        <div className="projects-page__content">
          {/* Page hero */}
          <div className="projects-hero">
            <div>
              <p className="projects-hero__eyebrow">What proves your hands-on engineering capability?</p>
              <h1 className="projects-hero__title">Projects</h1>
              {projects.length > 0 && (
                <div className="projects-hero__meta">
                  <span>Your project workspace</span>
                  <span className="projects-hero__meta-dot" />
                  <span>{projects.length} project{projects.length === 1 ? '' : 's'} on record</span>
                </div>
              )}
            </div>
          </div>

          <ProjectsHeader
            onAnalyzeAll={handleAnalyzeAll}
            analyzing={analyzing}
            projectCount={projects.length}
            interviewReadyCount={interviewReadyCount}
          />

          {error && <p className="projects-page__error">{error}</p>}

          <ProjectsStatsGrid stats={overview?.stats} />

          <div className="projects-page__columns">
            <div className="projects-page__col projects-page__col--main">
              <CollapsibleSection title="Project Gallery" subtitle="Large, evidence-rich work" defaultOpen={true}>
                <ProjectGallery
                  projects={projects}
                  loading={loading}
                  onOpenProject={handleOpenProject}
                  onAddProject={() => navigate('/profile')}
                  onViewDetails={setDetailProject}
                />
              </CollapsibleSection>

              {insights?.comparison && (
                <CollapsibleSection title="Compare & Recommend" dense defaultOpen={true}>
                  <CompareProjectsPanel comparison={insights.comparison} />
                </CollapsibleSection>
              )}

              {insights?.recommendations?.length > 0 && (
                <CollapsibleSection title="AI Recommendations" dense defaultOpen={false}>
                  <AIRecommendationsPanel recommendations={insights.recommendations} />
                </CollapsibleSection>
              )}
            </div>

            <div className="projects-page__col projects-page__col--side">
              <GoalAwareRankingPanel />

              <PortfolioNarrativePanel />

              <CollapsibleSection title="Interview Toolkit" dense defaultOpen={true}>
                <InterviewToolkitPanel featuredProjectName={featuredProject?.name} />
              </CollapsibleSection>

              <CollapsibleSection title="Evidence Coverage" dense defaultOpen={true}>
                <EvidenceCoveragePanel
                  coverage={insights?.source_coverage}
                  interviewReadyCount={interviewReadyCount}
                />
              </CollapsibleSection>

              <CollapsibleSection title="Recent Analysis" dense defaultOpen={false}>
                <RecentMilestonesPanel milestones={insights?.milestones} />
              </CollapsibleSection>
            </div>
          </div>
        </div>
      </div>

      {detailProject && (
        <ProjectDetailModal
          project={detailProject}
          onClose={() => setDetailProject(null)}
          onLinkConfirmed={loadAll}
        />
      )}
    </div>
  )
}

export default ProjectsPage