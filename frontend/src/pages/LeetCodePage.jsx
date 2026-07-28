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
import TopicBreakdown from '../components/leetcode/TopicBreakdown'
import PracticeHeatmap from '../components/leetcode/PracticeHeatmap'
import WeakAreas from '../components/leetcode/WeakAreas'
import DifficultyDistribution from '../components/leetcode/DifficultyDistribution'
import ContestPerformance from '../components/leetcode/ContestPerformance'
import EvidenceGenerated from '../components/leetcode/EvidenceGenerated'
import TodaysFocus from '../components/leetcode/TodaysFocus'
import CareerInsights from '../components/leetcode/CareerInsights'
import CombinedSignal from '../components/leetcode/CombinedSignal'
import RecruiterPerspective from '../components/leetcode/RecruiterPerspective'
import RecentActivity from '../components/leetcode/RecentActivity'
import ManualEntryModal from '../components/leetcode/ManualEntryModal'
import LeetcodeReviewPanel from '../components/leetcode/LeetcodeReviewPanel'

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
        setResult('leetcode', { ...data, username })
      }
    } catch (err) {
      setError(err.message || 'Sync failed.')
    } finally {
      setSyncing(false)
    }
  }

  async function handleManualSubmit(tagCounts) {
    const data = await submitLeetcodeManual(token, tagCounts)
    setResult('leetcode', { ...data, username })
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

  return (
    <div className="leetcode-layout">
      <Sidebar />
      <div className="leetcode-main">
        <BreadcrumbBar section="Profile" page="LeetCode" />

        <div className="leetcode-content">
          <LeetCodeHeader
            username={username}
            syncedAt={leetcode?.synced_at}
            connected={Boolean(leetcode)}
            onSync={handleSync}
            onManualEntry={() => setShowManual(true)}
            onDisconnect={handleDisconnect}
            syncing={syncing}
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
              <GroupedStatsBar
                totalSolved={summary?.total_solved}
                activeDays={summary?.active_days_last_30}
                easy={summary?.easy}
                medium={summary?.medium}
                hard={summary?.hard}
                contestRating={summary?.contest_rating}
              />

              <div className="leetcode-columns">
                <div className="leetcode-col leetcode-col--main">
                  <CollapsibleSection title="AI LeetCode Coach" defaultOpen={true}>
                    <LeetcodeReviewPanel
                      review={leetcode?.portfolio_review}
                      onRun={handleRunReview}
                      loading={reviewLoading}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Topic breakdown" subtitle="What your problem-solving history can genuinely support" defaultOpen={true}>
                    <TopicBreakdown topicMastery={topicMastery} />
                  </CollapsibleSection>

                  <CollapsibleSection title="Evidence generated" defaultOpen={true}>
                    <EvidenceGenerated topicMastery={topicMastery} />
                  </CollapsibleSection>

                  <CollapsibleSection title="Difficulty & contests" dense defaultOpen={false}>
                    <div className="leetcode-row-2">
                      <DifficultyDistribution
                        easy={summary?.easy}
                        medium={summary?.medium}
                        hard={summary?.hard}
                        insightText={insights?.difficulty_insight}
                      />
                      <ContestPerformance
                        rating={summary?.contest_rating}
                        globalRanking={summary?.global_ranking}
                        attendedContestsCount={summary?.attended_contests_count}
                      />
                    </div>
                  </CollapsibleSection>

                  <CollapsibleSection title="Recent activity" dense defaultOpen={false}>
                    <RecentActivity
                      skillEvidenceDetail={insights?.skill_evidence_detail}
                      progress={insights?.progress}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Recruiter perspective" dense defaultOpen={false}>
                    <RecruiterPerspective
                      totalSolved={summary?.total_solved}
                      topicMastery={topicMastery}
                      blindSpots={insights?.blind_spots}
                      consistency={insights?.practice_habits?.consistency}
                    />
                  </CollapsibleSection>
                </div>

                <div className="leetcode-col leetcode-col--side">
                  <CollapsibleSection title="Interview readiness" defaultOpen={true} dense>
                    <CareerInsights
                      topicMastery={topicMastery}
                      attendedContestsCount={summary?.attended_contests_count}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Today's focus" defaultOpen={true} dense>
                    <TodaysFocus recommendations={insights?.recommendations} />
                  </CollapsibleSection>

                  <CollapsibleSection title="Practice heatmap" dense defaultOpen={false}>
                    <PracticeHeatmap
                      currentStreak={summary?.current_streak}
                      longestStreak={summary?.longest_streak}
                      activeDaysLast30={summary?.active_days_last_30}
                    />
                  </CollapsibleSection>

                  <CollapsibleSection title="Weak areas" dense defaultOpen={false}>
                    <WeakAreas
                      topicMastery={topicMastery}
                      longestGapDays={summary?.longest_gap_days}
                    />
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