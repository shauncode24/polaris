import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listProjects, getProjectsInsights, getGoalAwareRanking } from '../api/projects'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import CollapsibleSection from '../components/common/CollapsibleSection'
import ProjectsHeader from '../components/projects/ProjectsHeader'
import ProjectsStatsGrid from '../components/projects/ProjectsStatsGrid'
import ProjectGallery from '../components/projects/ProjectGallery'
import AIRecommendationsPanel from '../components/projects/AIRecommendationsPanel'
import RecentMilestonesPanel from '../components/projects/RecentMilestonesPanel'
import EvidenceCoveragePanel from '../components/projects/EvidenceCoveragePanel'
import PortfolioNarrativePanel from '../components/projects/PortfolioNarrativePanel'
import ProjectDetailModal from '../components/projects/ProjectDetailModal'
import './ProjectsPage.css'

function ProjectsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview] = useState(null)
  const [insights, setInsights] = useState(null)
  const [leadProjectId, setLeadProjectId] = useState(null)
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [detailProject, setDetailProject] = useState(null)

  const loadAll = useCallback(async () => {
    setError('')
    try {
      const [overviewData, insightsData, rankingData] = await Promise.all([
        listProjects(token),
        getProjectsInsights(token),
        getGoalAwareRanking(token).catch(() => null),
      ])
      setOverview(overviewData)
      setInsights(insightsData)
      setLeadProjectId(rankingData?.ranked?.[0]?.project_id || null)
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
  const interviewReadyCount = projects.filter(
    (p) => p.tier === 'Flagship Project' || p.tier === 'Career Project'
  ).length

  return (
    <div className="projects-page">
      <Sidebar />
      <div className="projects-page__main">
        <BreadcrumbBar section="Projects" page="Overview" />

        {/* Single continuous vertical flow — no side columns. */}
        <div className="projects-page__content">
          <div className="projects-hero">
            <div>
              <h1 className="projects-hero__title">Projects</h1>
              <p className="projects-hero__eyebrow">What proves your hands-on engineering capability?</p>
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

          {/* Executive summary of the whole portfolio comes first —
              collapsed after the first visit is a later enhancement;
              for now it opens expanded since it's the most useful read. */}
          <PortfolioNarrativePanel />

          <section className="projects-page__section">
            <h2 className="projects-page__section-title">Engineering Portfolio</h2>
            <p className="projects-page__section-lead">
              One row per project — the recommended lead project is flagged inline.
            </p>
            <ProjectGallery
              projects={projects}
              loading={loading}
              leadProjectId={leadProjectId}
              onOpenProject={handleOpenProject}
              onAddProject={() => navigate('/profile')}
              onViewDetails={setDetailProject}
            />
          </section>

          {insights?.recommendations?.length > 0 && (
            <AIRecommendationsPanel recommendations={insights.recommendations} />
          )}

          <EvidenceCoveragePanel
            coverage={insights?.source_coverage}
            interviewReadyCount={interviewReadyCount}
          />

          <CollapsibleSection title="Recent Activity" dense defaultOpen={false}>
            <RecentMilestonesPanel milestones={insights?.milestones} />
          </CollapsibleSection>
        </div>
      </div>

      {detailProject && (
        <ProjectDetailModal
          project={detailProject}
          recommendations={insights?.recommendations}
          onClose={() => setDetailProject(null)}
          onLinkConfirmed={loadAll}
        />
)}
    </div>
  )
}

export default ProjectsPage