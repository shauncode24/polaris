import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { getGithubWorkspace, syncGithub, runGithubPortfolioReview } from '../api/github'
import { getProfileData } from '../api/profile'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import GitHubHeader from '../components/github/GitHubHeader'
import GitHubHealthCards from '../components/github/GitHubHealthCards'
import PortfolioReviewPanel from '../components/github/PortfolioReviewPanel'
import GitHubStatsStrip from '../components/github/GitHubStatsStrip'
import RepositoryActivity from '../components/github/RepositoryActivity'
import ActivityTimeline from '../components/github/ActivityTimeline'
import RepositoryExplorer from '../components/github/RepositoryExplorer'
import LanguageAnalytics from '../components/github/LanguageAnalytics'
import CodingInsights from '../components/github/CodingInsights'
import AIRecommendations from '../components/github/AIRecommendations'
import GitHubResumeCoverage from '../components/github/GitHubResumeCoverage'
import SyncHistory from '../components/github/SyncHistory'
import GitHubConnectPanel from '../components/github/GitHubConnectPanel'
import CollapsibleSection from '../components/common/CollapsibleSection'
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

  const [resumeProjectNames, setResumeProjectNames] = useState([])
  const [resumeLoading, setResumeLoading] = useState(true)

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

  useEffect(() => {
    let cancelled = false
    setResumeLoading(true)
    getProfileData(token)
      .then((data) => {
        if (cancelled) return
        setResumeProjectNames((data.projects || []).map((p) => p.name).filter(Boolean))
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setResumeLoading(false) })
    return () => { cancelled = true }
  }, [token])

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

  const healthMetrics = [
    { label: 'Repository score', value: avgScore, tone: quality.tone },
    { label: 'Engineering activity', value: activity.label, tone: activity.tone },
    { label: 'Code quality', value: quality.label, tone: quality.tone },
    { label: 'Documentation', value: documentation.label, tone: documentation.tone },
    { label: 'Portfolio strength', value: portfolio.label, tone: portfolio.tone },
  ]

  const statItems = [
    { label: 'Repositories', value: summary.repos_synced ?? repositories.length },
    { label: 'Commits (30d)', value: summary.total_commits_last_30_days ?? 0 },
    { label: 'Languages', value: (summary.languages_detected || []).length },
    { label: 'Stars', value: summary.total_stars ?? 0 },
    { label: 'Forks', value: summary.total_forks ?? 0 },
    { label: 'Active repos', value: insights.engineering_practices?.maintenance?.active_projects ?? 0 },
  ]

  return (
    <div className="github-layout">
      <Sidebar />
      <div className="github-main">
        <TopBar section="Profile" page="GitHub" />

        <div className="github-content">
          <GitHubHeader
            username={workspace?.username || user?.github_username}
            repoCount={repositories.length}
            syncedAt={workspace?.synced_at}
            connected={hasData}
            syncing={syncing}
            onSync={handleSync}
            onAnalyze={handleSync}
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
                  { label: 'Activity', value: activity.label, tone: activity.tone, breakdown: { '30d commits': summary.total_commits_last_30_days ?? 0, 'Formula (Heuristic ⓘ)': 'Commits / 20 per repo' } },
                  { label: 'Documentation', value: documentation.label, tone: documentation.tone, breakdown: { 'With README': `${insights.engineering_practices?.documentation?.repos_with_readme ?? 0} / ${repositories.length}`, 'Formula': '% of repos with README' } },
                  { label: 'Portfolio', value: portfolio.label, tone: portfolio.tone, breakdown: { 'Repositories': repositories.length, 'Avg Score': `${avgScore}/100`, 'Formula': 'Average of all repo scores' } },
                  { label: 'Hygiene', value: quality.label, tone: quality.tone, breakdown: { 'Readme Weight': '30%', 'Tests Weight': '40%', 'CI Weight': '30%', 'Formula (Heuristic ⓘ)': '0.3*README + 0.4*Tests + 0.3*CI' } },
                ]}
              />

              <CollapsibleSection title="AI Portfolio Review" defaultOpen={true}>
                {reviewError && <p className="github-error">{reviewError}</p>}
                <PortfolioReviewPanel
                  review={workspace?.portfolio_review}
                  onRun={handleRunReview}
                  loading={reviewLoading}
                />
              </CollapsibleSection>

              <CollapsibleSection title="Stats" dense defaultOpen={false}>
                <GitHubStatsStrip stats={statItems} />
              </CollapsibleSection>

              <CollapsibleSection title="Activity" dense defaultOpen={false}>
                <div className="github-columns">
                  <RepositoryActivity repositories={repositories} />
                  <ActivityTimeline repositories={repositories} />
                </div>
              </CollapsibleSection>

              <CollapsibleSection title="Repository Explorer" defaultOpen={true}>
                <RepositoryExplorer repositories={repositories} />
              </CollapsibleSection>

              <CollapsibleSection title="Languages & Engineering Habits" dense defaultOpen={false}>
                <div className="github-columns">
                  <LanguageAnalytics languages={summary.languages_detected || []} />
                  <CodingInsights insights={insights} />
                </div>
              </CollapsibleSection>

              <CollapsibleSection title="Recommendations" defaultOpen={true}>
                <AIRecommendations
                  repositories={repositories}
                  insightRecommendations={insights.recommendations}
                />
              </CollapsibleSection>

              <CollapsibleSection title="GitHub → Resume" dense defaultOpen={true}>
                <div className="github-columns">
                  <GitHubResumeCoverage
                    repositories={repositories}
                    resumeProjectNames={resumeProjectNames}
                    loading={resumeLoading}
                  />
                  <SyncHistory syncedAt={workspace?.synced_at} summary={summary} />
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