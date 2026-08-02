import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { listProjects, getProjectsInsights, getGoalAwareRanking, getPortfolioNarrative } from '../api/projects'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ProjectsHeader from '../components/projects/ProjectsHeader'
import ProjectsStatsGrid from '../components/projects/ProjectsStatsGrid'
import PortfolioNarrativePanel from '../components/projects/PortfolioNarrativePanel'
import EvidenceCoveragePanel from '../components/projects/EvidenceCoveragePanel'
import LinkSuggestionsPanel from '../components/projects/LinkSuggestionsPanel'
import ProjectPortfolioList from '../components/projects/ProjectPortfolioList'
import ProjectInspector from '../components/projects/ProjectInspector'
import AIRecommendationsPanel from '../components/projects/AIRecommendationsPanel'
import RecentMilestonesPanel from '../components/projects/RecentMilestonesPanel'
import './ProjectsPage.css'

// Redesign notes (see PROJECTS MODULE — COMPLETE UI/UX REDESIGN doc):
// - Portfolio Narrative moved to the very top, right below the header, as
//   the page's executive summary — paired with a compact Evidence
//   Coverage widget beside it instead of both fighting for attention
//   further down the page.
// - The 2x2 ProjectGallery/ProjectCard grid is replaced by
//   ProjectPortfolioList (single-column ProjectRow entries).
// - The centered ProjectDetailModal is replaced by ProjectInspector, a
//   persistent right-side panel that swaps content in place when a
//   different project is selected instead of closing/reopening.
// - The dedicated "Which project should lead?" (GoalAwareRankingPanel) and
//   "Compare projects" (CompareProjectsPanel) sections are removed as
//   standalone blocks: the top-ranked project is now badged inline on its
//   ProjectRow via `leadProjectId`, and comparison now lives inside the
//   inspector's Project Intelligence section (comparisonTarget field).
// - The standalone InterviewToolkitPanel is removed; its prompts moved
//   into the inspector's Interview Toolkit section, scoped to whichever
//   project is open.
// - RecentMilestonesPanel now self-collapses (defaultOpen=false) and sits
//   at the bottom of the page.
function ProjectsPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview] = useState(null)
  const [insights, setInsights] = useState(null)
  const [ranking, setRanking] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [selectedProject, setSelectedProject] = useState(null)

  const loadCore = useCallback(async () => {
    setError('')
    try {
      const [overviewData, insightsData, rankingData] = await Promise.all([
        listProjects(token),
        getProjectsInsights(token),
        getGoalAwareRanking(token),
      ])
      setOverview(overviewData)
      setInsights(insightsData)
      setRanking(rankingData)
      // Keep the inspector's project fresh if the user has one open
      // (e.g. after confirming a repo link or regenerating a report).
      setSelectedProject((prev) => {
        if (!prev) return prev
        return overviewData.projects.find((p) => p.id === prev.id) || null
      })
    } catch (err) {
      setError(err.message || 'Could not load your projects.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    loadCore()
  }, [loadCore])

  const projects = overview?.projects || []
  const leadProjectId = ranking?.ranked?.[0]?.project_id || null

  // NOTE: There's no explicit `interview_ready` flag on ProjectCard from
  // the backend (see overview.py) and no dedicated "analyze all" endpoint
  // in api/projects.js. This is a client-side heuristic — verified GitHub
  // evidence with no unresolved high-severity claim risk — standing in
  // for "ready to discuss in an interview" until/unless the backend adds
  // a real field for it.
  const interviewReadyCount = useMemo(
    () => projects.filter((p) => p.has_repo && p.claim_risk !== 'high').length,
    [projects]
  )

  // "Analyze Portfolio" re-runs the two reports that actually reflect
  // fresh analysis across the whole portfolio (narrative + ranking), then
  // reloads everything else so the page is fully in sync.
  async function handleAnalyzeAll() {
    setAnalyzing(true)
    setError('')
    try {
      await getPortfolioNarrative(token, true)
      await loadCore()
    } catch (err) {
      setError(err.message || 'Could not re-analyze your portfolio.')
    } finally {
      setAnalyzing(false)
    }
  }

  function handleInterview(project) {
    navigate(`/interview?prefill=${encodeURIComponent(`Tell me about ${project.name}.`)}`)
  }

  return (
    <div className="projects-page">
      <Sidebar />
      <div className="projects-page__main">
        <TopBar section="Profile" page="Projects" notificationCount={0} />

        <div className="projects-page__content">
          <ProjectsHeader
            onAnalyzeAll={handleAnalyzeAll}
            analyzing={analyzing}
            projectCount={overview?.stats?.total}
            interviewReadyCount={interviewReadyCount}
          />

          {error && <p className="projects-page__error">{error}</p>}

          <ProjectsStatsGrid stats={overview?.stats} />

          <LinkSuggestionsPanel onLinked={loadCore} />

          <div className="projects-page__health-row">
            <PortfolioNarrativePanel />
            <EvidenceCoveragePanel
              coverage={insights?.source_coverage}
              interviewReadyCount={interviewReadyCount}
            />
          </div>

          {insights?.comparison?.recommendation && (
            <p className="projects-page__dilution-warning">{insights.comparison.recommendation}</p>
          )}

          <ProjectPortfolioList
            projects={projects}
            loading={loading}
            leadProjectId={leadProjectId}
            selectedProjectId={selectedProject?.id}
            onSelect={setSelectedProject}
            onInterview={handleInterview}
            onAddProject={() => navigate('/profile')}
          />

          <AIRecommendationsPanel recommendations={insights?.recommendations} />

          <RecentMilestonesPanel milestones={insights?.milestones} />
        </div>
      </div>

      {selectedProject && (
        <ProjectInspector
          project={selectedProject}
          onClose={() => setSelectedProject(null)}
          onLinkConfirmed={loadCore}
        />
      )}
    </div>
  )
}

export default ProjectsPage