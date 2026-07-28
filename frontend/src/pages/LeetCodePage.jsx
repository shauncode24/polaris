// frontend/src/pages/LeetCodePage.jsx
import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { syncLeetcode, submitLeetcodeManual } from '../api/profile'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import EmptyState from '../components/common/EmptyState'

import LeetCodeHeader from '../components/leetcode/LeetCodeHeader'
import StatsGrid from '../components/leetcode/StatsGrid'
import TopicBreakdown from '../components/leetcode/TopicBreakdown'
import PracticeHeatmap from '../components/leetcode/PracticeHeatmap'
import WeakAreas from '../components/leetcode/WeakAreas'
import DifficultyDistribution from '../components/leetcode/DifficultyDistribution'
import ContestPerformance from '../components/leetcode/ContestPerformance'
import EvidenceGenerated from '../components/leetcode/EvidenceGenerated'
import TodaysFocus from '../components/leetcode/TodaysFocus'
import CareerInsights from '../components/leetcode/CareerInsights'
import RecentActivity from '../components/leetcode/RecentActivity'
import ManualEntryModal from '../components/leetcode/ManualEntryModal'

import './LeetCodePage.css'

function LeetCodePage() {
  const { token, user } = useAuth()
  const { results, setResult } = useProfileData()
  const leetcode = results.leetcode

  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState('')
  const [showManual, setShowManual] = useState(false)

  const username = leetcode?.username || user?.leetcode_username || ''

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

  function handleDisconnect() {
    setResult('leetcode', null)
  }

  const insights = leetcode?.insights
  const summary = leetcode?.summary

  const stats = leetcode
    ? [
        { label: 'Problems solved', value: summary?.total_solved ?? 0 },
        { label: 'Easy', value: summary?.easy ?? 0 },
        { label: 'Medium', value: summary?.medium ?? 0 },
        { label: 'Hard', value: summary?.hard ?? 0 },
        { label: 'Active days (30d)', value: summary?.active_days_last_30 ?? 0 },
        { label: 'Contest rating', value: summary?.contest_rating != null ? Math.round(summary.contest_rating) : 'Unrated' },
      ]
    : []

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
              <StatsGrid stats={stats} />

              <div className="leetcode-columns">
                <div className="leetcode-col leetcode-col--main">
                  <TopicBreakdown topicMastery={insights?.topic_mastery} />

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

                  <EvidenceGenerated topicMastery={insights?.topic_mastery} />
                  <RecentActivity
                    skillEvidenceDetail={insights?.skill_evidence_detail}
                    progress={insights?.progress}
                  />
                </div>

                <div className="leetcode-col leetcode-col--side">
                  <PracticeHeatmap
                    currentStreak={summary?.current_streak}
                    longestStreak={summary?.longest_streak}
                    activeDaysLast30={summary?.active_days_last_30}
                  />
                  <WeakAreas
                    topicMastery={insights?.topic_mastery}
                    longestGapDays={summary?.longest_gap_days}
                  />
                  <TodaysFocus recommendations={insights?.recommendations} />
                  <CareerInsights
                    blindSpots={insights?.blind_spots}
                    attendedContestsCount={summary?.attended_contests_count}
                  />
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