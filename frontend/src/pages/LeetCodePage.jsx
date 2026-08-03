import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { syncLeetcode, submitLeetcodeManual, getLeetcodeWorkspace, runLeetcodePortfolioReview } from '../api/profile'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import EmptyState from '../components/common/EmptyState'
import CollapsibleSection from '../components/common/CollapsibleSection'

import LeetCodeHeader from '../components/leetcode/LeetCodeHeader'
import GroupedStatsBar from '../components/leetcode/GroupedStatsBar'
import LeetcodeReviewPanel from '../components/leetcode/LeetcodeReviewPanel'
import PracticeRecommendations from '../components/leetcode/PracticeRecommendations'
import EngineeringProgress from '../components/leetcode/EngineeringProgress'
import TopicBreakdown from '../components/leetcode/TopicBreakdown'
import CompanyReadiness from '../components/leetcode/CompanyReadiness'
import RecentActivity from '../components/leetcode/RecentActivity'
import ResumeClaimsCheck from '../components/leetcode/ResumeClaimsCheck'

import CareerInsights from '../components/leetcode/CareerInsights'
import PracticeOverview from '../components/leetcode/PracticeOverview'
import PracticeDiversity from '../components/leetcode/PracticeDiversity'
import WeakAreas from '../components/leetcode/WeakAreas'
import CombinedSignal from '../components/leetcode/CombinedSignal'

import ManualEntryModal from '../components/leetcode/ManualEntryModal'
import DataCeilingNote from '../components/leetcode/DataCeilingNote'

import './LeetCodePage.css'

function LeetCodePage() {
  const { token, user } = useAuth()
  const { results, setResult } = useProfileData()
  const leetcode = results.leetcode

  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [showManual, setShowManual] = useState(false)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [loadingWorkspace, setLoadingWorkspace] = useState(false)

  const username = leetcode?.username || user?.leetcode_username || ''

  useEffect(() => {
    let cancelled = false
    setLoadingWorkspace(true)
    getLeetcodeWorkspace(token)
      .then((data) => {
        if (!cancelled && data && data.has_data) {
          setResult('leetcode', data)
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingWorkspace(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  async function handleSync() {
    if (!username) {
      setError('No LeetCode username on file yet — use manual entry or connect via Build Profile.')
      return
    }
    setSyncing(true)
    setError('')
    try {
      const data = await syncLeetcode(token, { username })
      if (data.status === 'degraded') {
        setError(data.reason || 'LeetCode sync is temporarily unavailable — try manual entry.')
      } else {
        const workspace = await getLeetcodeWorkspace(token)
        setResult('leetcode', workspace && workspace.has_data ? workspace : { ...data, username })
      }
    } catch (err) {
      setError(err.message || 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  async function handleManualSubmit(tagCounts) {
    await submitLeetcodeManual(token, tagCounts)
    const workspace = await getLeetcodeWorkspace(token)
    setResult('leetcode', workspace && workspace.has_data ? workspace : { username })
    setShowManual(false)
  }

  async function handleRunReview() {
    setReviewLoading(true)
    setError('')
    try {
      const reviewReport = await runLeetcodePortfolioReview(token)
      setResult('leetcode', {
        ...leetcode,
        portfolio_review: reviewReport,
      })
    } catch (err) {
      setError(err.message || 'Failed to generate review.')
    } finally {
      setReviewLoading(false)
    }
  }

  function handleDisconnect() {
    setResult('leetcode', null)
  }

  const insights = leetcode?.insights
  const summary = leetcode?.summary
  const topicMastery = insights?.topic_mastery || []
  const practiceHabits = insights?.practice_habits

  return (
    <div className="leetcode-layout">
      <Sidebar />
      <div className="leetcode-main">
        <BreadcrumbBar section="Profile" page="LeetCode" />

        <div className="leetcode-content">
          {/* Page hero */}
          <div className="leetcode-hero">
            <div>
              <h1 className="leetcode-hero__title">LeetCode</h1>
              <p className="leetcode-hero__eyebrow">How robust is your data structures & algorithms practice?</p>
            </div>
          </div>

          <LeetCodeHeader
            username={username}
            syncedAt={leetcode?.synced_at}
            connected={Boolean(leetcode)}
            onSync={handleSync}
            onManualEntry={() => setShowManual(true)}
            onDisconnect={handleDisconnect}
            onRunReview={handleRunReview}
            syncing={syncing}
            reviewLoading={reviewLoading}
            totalSolved={summary?.total_solved}
            contestRating={summary?.contest_rating}
          />

          {error && <p className="leetcode-error">{error}</p>}

          {!leetcode ? (
            <EmptyState
              message="No LeetCode data yet — sync your account or add counts manually to generate interview-readiness evidence."
              ctaLabel="Sync now"
              onCta={handleSync}
            />
          ) : (
            <>
              {/* 2. Overview metrics */}
              <GroupedStatsBar
                totalSolved={summary?.total_solved}
                activeDays={summary?.active_days_last_30}
                easy={summary?.easy}
                medium={summary?.medium}
                hard={summary?.hard}
                contestRating={summary?.contest_rating}
              />

              <DataCeilingNote note={insights?.data_ceiling_note} />

              <div className="leetcode-columns">
                <div className="leetcode-col leetcode-col--main">
                  {/* 3. AI Coach — merged with Recruiter Perspective */}
                  <CollapsibleSection title="AI LeetCode Coach" defaultOpen={true}>
                    <LeetcodeReviewPanel
                      review={leetcode?.portfolio_review}
                      onRun={handleRunReview}
                      loading={reviewLoading}
                      totalSolved={summary?.total_solved}
                      topicMastery={topicMastery}
                      blindSpots={insights?.blind_spots}
                    />
                  </CollapsibleSection>

                  {/* 4. Practice Recommendations — moved up, highest-value action */}
                  <CollapsibleSection title="Practice recommendations" dense defaultOpen={true}>
                    <PracticeRecommendations recommendations={insights?.recommendations} />
                  </CollapsibleSection>

                  {/* 5. Engineering Progress — quadrant + history, merged & shrunk */}
                  <CollapsibleSection title="Engineering progress" subtitle="LeetCode vs. GitHub, fused into one signal" defaultOpen={true}>
                    <EngineeringProgress
                      quadrant={leetcode?.engineering_quadrant}
                      history={leetcode?.engineering_history}
                    />
                  </CollapsibleSection>

                  {/* 6. Topic Breakdown — merged with Evidence Generated */}
                  <CollapsibleSection title="Topic breakdown" subtitle="What your problem-solving history can genuinely support" defaultOpen={true}>
                    <TopicBreakdown topicMastery={topicMastery} />
                  </CollapsibleSection>

                  {/* 7. Company Readiness — collapsed, top/bottom 5 */}
                  <CollapsibleSection title="Company readiness" defaultOpen={false}>
                    <CompanyReadiness companyReadiness={leetcode?.company_readiness} />
                  </CollapsibleSection>

                  {/* 8. Recent Activity — collapsed */}
                  <CollapsibleSection title="Recent activity" dense defaultOpen={false}>
                    <RecentActivity
                      skillEvidenceDetail={insights?.skill_evidence_detail}
                      progress={insights?.progress}
                      planAdherence={insights?.plan_adherence}
                    />
                  </CollapsibleSection>

                  {/* 9. Resume Impact — collapsed, compressed verdict card */}
                  <CollapsibleSection title="Resume impact" dense defaultOpen={false}>
                    <ResumeClaimsCheck resumeClaims={leetcode?.resume_claims} />
                  </CollapsibleSection>
                </div>

                <div className="leetcode-col leetcode-col--side">
                  <CollapsibleSection title="Interview readiness" defaultOpen={true} dense>
                    <CareerInsights
                      topicMastery={topicMastery}
                      attendedContestsCount={summary?.attended_contests_count}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Practice overview" dense defaultOpen={true}>
                    <PracticeOverview
                      currentStreak={summary?.current_streak}
                      longestStreak={summary?.longest_streak}
                      activeDaysLast30={summary?.active_days_last_30}
                      preferredDifficulty={practiceHabits?.preferred_difficulty}
                      averageSessionLength={practiceHabits?.average_session_length}
                      easy={summary?.easy}
                      medium={summary?.medium}
                      hard={summary?.hard}
                      rating={summary?.contest_rating}
                      attendedContestsCount={summary?.attended_contests_count}
                      trajectory={insights?.contest_trajectory}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Practice diversity" dense defaultOpen={true}>
                    <PracticeDiversity diversity={insights?.practice_diversity} />
                  </CollapsibleSection>

                  <CollapsibleSection title="Weak areas" dense defaultOpen={false}>
                    <WeakAreas topicMastery={topicMastery} />
                  </CollapsibleSection>

                  <CollapsibleSection title="Combined signal" dense defaultOpen={false}>
                    <CombinedSignal topicMastery={topicMastery} />
                  </CollapsibleSection>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {showManual && (
        <ManualEntryModal onClose={() => setShowManual(false)} onSubmit={handleManualSubmit} />
      )}
    </div>
  )
}

export default LeetCodePage