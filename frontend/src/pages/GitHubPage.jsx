import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { getGithubWorkspace, syncGithub, runGithubPortfolioReview } from '../api/github'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import GitHubHeader from '../components/github/GitHubHeader'
import GitHubHealthCards from '../components/github/GitHubHealthCards'
import PortfolioReviewPanel from '../components/github/PortfolioReviewPanel'
import RepositoryActivity from '../components/github/RepositoryActivity'
import ActivityTimeline from '../components/github/ActivityTimeline'
import RepositoryExplorer from '../components/github/RepositoryExplorer'
import GitHubConnectPanel from '../components/github/GitHubConnectPanel'
import CollapsibleSection from '../components/common/CollapsibleSection'
import ArchitectureMaturityCard from '../components/github/ArchitectureMaturityCard'
import TechnologyExpertiseCard from '../components/github/TechnologyExpertiseCard'
import PortfolioProfileCard from '../components/github/PortfolioProfileCard'
import './GitHubPage.css'

function scoreLabel(score) {
  if (score >= 85) return { label: 'Excellent', tone: 'high' }
  if (score >= 70) return { label: 'Good', tone: 'high' }
  if (score >= 50) return { label: 'Medium', tone: 'medium' }
  return { label: 'Needs work', tone: 'low' }
}

function activityLabel(commits30d) {
  if (commits30d >= 80) return { label: 'High', tone: 'high' }
  if (commits30d >= 20) return { label: 'Moderate', tone: 'medium' }
  if (commits30d > 0) return { label: 'Low', tone: 'low' }
  return { label: 'Inactive', tone: 'low' }
}

function strengthLabel(score) {
  if (score >= 80) return { label: 'Strong', tone: 'high' }
  if (score >= 60) return { label: 'Solid', tone: 'medium' }
  if (score >= 40) return { label: 'Growing', tone: 'medium' }
  return { label: 'Early stage', tone: 'low' }
}

function GitHubPage() {
  const { token, user } = useAuth()
  const { setResult } = useProfileData()

  const [workspace, setWorkspace] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [syncing, setSyncing] = useState(false)
  const [connectError, setConnectError] = useState('')

  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewError, setReviewError] = useState('')

  const loadWorkspace = useCallback(async () => {
    try {
      const data = await getGithubWorkspace(token)
      setWorkspace(data)
    } catch (e) {
      setError(e.message || 'Could not load your GitHub data.')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    loadWorkspace()
  }, [loadWorkspace])

  function applySyncResult(username, data) {
    const normalized = {
      has_data: true,
      username,
      synced_at: data.synced_at,
      summary: data.summary,
      repositories: data.repositories,
      insights: data.insights,
      portfolio_review: workspace?.portfolio_review || null,
    }
    setWorkspace(normalized)
    setResult('github', { ...data, username })
  }

  async function handleSync() {
    const username = workspace?.username || user?.github_username
    if (!username) return
    setSyncing(true)
    setError('')
    try {
      const data = await syncGithub(token, { username })
      applySyncResult(username, data)
    } catch (e) {
      setError(e.message || 'GitHub sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  async function handleConnect(username, pat) {
    setSyncing(true)
    setConnectError('')
    try {
      const data = await syncGithub(token, { username, githubToken: pat || undefined })
      applySyncResult(username, data)
    } catch (e) {
      setConnectError(e.message || 'GitHub sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  async function handleRunReview() {
    setReviewLoading(true)
    setReviewError('')
    try {
      const review = await runGithubPortfolioReview(token)
      setWorkspace((prev) => ({ ...prev, portfolio_review: review }))
    } catch (e) {
      setReviewError(e.message || 'Could not generate the portfolio review.')
    } finally {
      setReviewLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="github-layout">
        <Sidebar />
        <div className="github-main">
          <TopBar section="Profile" page="GitHub" />
          <div className="github-content">
            <p className="github-loading">Loading your GitHub data…</p>
          </div>
        </div>
      </div>
    )
  }

  const hasData = Boolean(workspace?.has_data)
  const repositories = workspace?.repositories || []
  const summary = workspace?.summary || {}
  const insights = workspace?.insights || {}

  const avgScore = repositories.length > 0
    ? Math.round(
        repositories.reduce((sum, r) => sum + (r.project_score?.overall || 0), 0) / repositories.length
      )
    : 0
  const quality = scoreLabel(avgScore)
  const activity = activityLabel(summary.total_commits_last_30_days || 0)
  const docScore = insights.engineering_practices?.documentation?.score ?? 0
  const documentation = scoreLabel(docScore)
  const portfolio = strengthLabel(avgScore)

  return (
    <div className="github-layout">
      <Sidebar />
      <div className="github-main">
        <TopBar section="Profile" page="GitHub" />

        <div className="github-content">
          {/* Page hero */}
          <div className="github-hero">
            <div>
              <h1 className="github-hero__title">GitHub</h1>
              <p className="github-hero__eyebrow">How strong is your open source footprint?</p>
            </div>
          </div>

          {/* ── 1. HEADER ─────────────────────────────── */}
          <GitHubHeader
            username={workspace?.username || user?.github_username}
            repoCount={repositories.length}
            syncedAt={workspace?.synced_at}
            connected={hasData}
            syncing={syncing}
            onSync={handleSync}
            onAnalyze={handleSync}
            onRunReview={handleRunReview}
            reviewLoading={reviewLoading}
            avgScore={avgScore}
            commits30d={summary.total_commits_last_30_days ?? 0}
          />

          {error && <p className="github-error">{error}</p>}

          {!hasData ? (
            <GitHubConnectPanel
              defaultUsername={user?.github_username}
              onConnect={handleConnect}
              connecting={syncing}
              error={connectError}
            />
          ) : (
            <>
              <GitHubHealthCards
                overall={avgScore}
                overallLabel={quality.label}
                overallTone={quality.tone}
                metrics={[
                  {
                    label: 'Activity',
                    value: activity.label,
                    tone: activity.tone,
                    progress: Math.min(100, Math.round(((summary.total_commits_last_30_days || 0) / 80) * 100)),
                    sentence: `${summary.total_commits_last_30_days ?? 0} commits across your repos in the last 30 days.`,
                    breakdown: { '30d commits': summary.total_commits_last_30_days ?? 0, 'Formula (Heuristic ⓘ)': 'Commits / 20 per repo' },
                  },
                  {
                    label: 'Documentation',
                    value: documentation.label,
                    tone: documentation.tone,
                    progress: docScore,
                    sentence: `${insights.engineering_practices?.documentation?.repos_with_readme ?? 0} of ${repositories.length} repos have a README.`,
                    breakdown: { 'With README': `${insights.engineering_practices?.documentation?.repos_with_readme ?? 0} / ${repositories.length}`, 'Formula': '% of repos with README' },
                  },
                  {
                    label: 'Portfolio',
                    value: portfolio.label,
                    tone: portfolio.tone,
                    progress: avgScore,
                    sentence: `Averaging ${avgScore}/100 across ${repositories.length} synced repositor${repositories.length === 1 ? 'y' : 'ies'}.`,
                    breakdown: { 'Repositories': repositories.length, 'Avg Score': `${avgScore}/100`, 'Formula': 'Average of all repo scores' },
                  },
                  {
                    label: 'Hygiene',
                    value: quality.label,
                    tone: quality.tone,
                    progress: avgScore,
                    sentence: 'Blends README coverage, tests, and CI presence into one read.',
                    breakdown: { 'Readme Weight': '30%', 'Tests Weight': '40%', 'CI Weight': '30%', 'Formula (Heuristic ⓘ)': '0.3*README + 0.4*Tests + 0.3*CI' },
                  },
                ]}
              />

              {/* ── 2. AI PORTFOLIO REVIEW ───────────────── */}
              <CollapsibleSection title="AI Portfolio Review" subtitle="Summary · strengths · role fit · next steps" defaultOpen={true}>
                {reviewError && <p className="github-error">{reviewError}</p>}
                <PortfolioReviewPanel
                  review={workspace?.portfolio_review}
                  onRun={handleRunReview}
                  loading={reviewLoading}
                  recommendations={insights.recommendations || []}
                />
              </CollapsibleSection>

              {/* ── 3. ENGINEERING INTELLIGENCE ──────────── */}
              <CollapsibleSection title="Engineering Intelligence" subtitle="Architecture, technology depth, and portfolio profile" defaultOpen={true}>
                <div className="github-columns">
                  <ArchitectureMaturityCard insights={insights} />
                  <PortfolioProfileCard insights={insights} />
                </div>
                <TechnologyExpertiseCard
                  technologyDepth={insights.technology_depth || {}}
                  skillConfidenceExplanations={workspace?.portfolio_review?.skill_confidence_explanations || []}
                  languages={summary.languages_detected || []}
                />
              </CollapsibleSection>

              {/* ── 4. REPOSITORY EXPLORER ───────────────── */}
              <CollapsibleSection title="Repository Explorer" subtitle="The raw evidence behind every score above" defaultOpen={true}>
                <RepositoryExplorer repositories={repositories} />
              </CollapsibleSection>

              {/* ── 5. ACTIVITY ──────────────────────────── */}
              <CollapsibleSection title="Activity" dense defaultOpen={false}>
                <div className="github-columns">
                  <RepositoryActivity repositories={repositories} />
                  <ActivityTimeline repositories={repositories} />
                </div>
              </CollapsibleSection>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default GitHubPage