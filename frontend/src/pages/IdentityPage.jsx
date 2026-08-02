// frontend/src/pages/IdentityPage.jsx
import { useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import {
  getEngineeringIdentity,
  refreshEngineeringIdentity,
  getIdentityHistory,
  getWeeklyBrief,
  refreshWeeklyBrief,
} from '../api/identity'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import CollapsibleSection from '../components/common/CollapsibleSection'
import IdentityHero from '../components/identity/IdentityHero'
import RoleFitBars from '../components/identity/RoleFitBars'
import SignalsGapsPanel from '../components/identity/SignalsGapsPanel'
import RecommendedFocusCard from '../components/identity/RecommendedFocusCard'
import TechDepthGrid from '../components/identity/TechDepthGrid'
import WeeklyBriefCard from '../components/identity/WeeklyBriefCard'
import ProfileSnapshotStrip from '../components/identity/ProfileSnapshotStrip'
import GithubDeepDivePanel from '../components/identity/GithubDeepDivePanel'
import LeetcodeInsightsPanel from '../components/identity/LeetcodeInsightsPanel'
import CoverageTimelinePanel from '../components/identity/CoverageTimelinePanel'
import GoalsMatchesPanel from '../components/identity/GoalsMatchesPanel'
import ClaimFreshnessPanel from '../components/identity/ClaimFreshnessPanel'
import IdentityHistoryPanel from '../components/identity/IdentityHistoryPanel'
import './IdentityPage.css'

export default function IdentityPage() {
  const { token } = useAuth()

  const [identity, setIdentity] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const [history, setHistory] = useState([])

  const [brief, setBrief] = useState(null)
  const [briefLoading, setBriefLoading] = useState(false)
  const [briefError, setBriefError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await getEngineeringIdentity(token)
        if (!cancelled) setIdentity(data)
      } catch {
        // 404 = never generated yet — leave identity null, empty state handles it
      } finally {
        if (!cancelled) setLoading(false)
      }

      try {
        const historyData = await getIdentityHistory(token, 10)
        if (!cancelled) setHistory(historyData)
      } catch {
        // no history yet — non-fatal
      }

      try {
        const briefData = await getWeeklyBrief(token)
        if (!cancelled) setBrief(briefData)
      } catch {
        // 404 = never generated yet — fine, empty state handles it
      }
    }

    load()
    return () => { cancelled = true }
  }, [token])

  async function handleRefreshIdentity() {
    setRefreshing(true)
    setError(null)
    try {
      const data = await refreshEngineeringIdentity(token)
      setIdentity(data)
      try {
        const historyData = await getIdentityHistory(token, 10)
        setHistory(historyData)
      } catch {
        // non-fatal
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  async function handleRefreshBrief() {
    setBriefLoading(true)
    setBriefError(null)
    try {
      const data = await refreshWeeklyBrief(token)
      setBrief(data)
    } catch (e) {
      setBriefError(e.message)
    } finally {
      setBriefLoading(false)
    }
  }

  const facts = identity?.facts
  const narrative = identity?.narrative

  return (
    <div className="identity-layout">
      <Sidebar />
      <div className="identity-main">
        <BreadcrumbBar section="Overview" page="Engineering Identity" />

        <div className="identity-content">
          {loading && (
            <div className="identity-loading">
              <div className="identity-spinner" />
              <span>Loading your engineering identity…</span>
            </div>
          )}

          {!loading && !identity && (
            <div className="identity-empty-state">
              <h2>No Engineering Identity yet</h2>
              <p>
                This reconciles your Resume, GitHub, and LeetCode evidence into one synthesized view —
                generate it once you've synced at least one of those sources.
              </p>
              <button
                type="button"
                className="identity-hero__btn"
                onClick={handleRefreshIdentity}
                disabled={refreshing}
              >
                {refreshing ? 'Synthesizing…' : 'Generate Identity'}
              </button>
              {error && <p className="weekly-brief__error">{error}</p>}
            </div>
          )}

          {!loading && identity && (
            <>
              {error && <p className="weekly-brief__error">{error}</p>}

              <IdentityHero
                narrative={narrative}
                generatedAt={identity.generated_at}
                degraded={identity.analysis_degraded}
                sourceEvent={identity.source_event}
                isInvalidated={identity.is_invalidated}
                invalidatedReason={identity.invalidated_reason}
                invalidatedAt={identity.invalidated_at}
                onRefresh={handleRefreshIdentity}
                refreshing={refreshing}
              />

              <ProfileSnapshotStrip facts={facts} />

              <div className="identity-columns">
                <div className="identity-col">
                  <CollapsibleSection title="Role Fit" defaultOpen={true}>
                    <RoleFitBars roleFit={facts?.role_fit} />
                  </CollapsibleSection>

                  <SignalsGapsPanel
                    strongestSignals={narrative?.strongest_signals}
                    biggestGaps={narrative?.biggest_gaps}
                    contradictions={narrative?.contradictions}
                  />

                  <RecommendedFocusCard text={narrative?.recommended_focus} />

                  <CollapsibleSection title="Technology Depth" defaultOpen={false}>
                    <TechDepthGrid highlights={facts?.technology_depth_highlights} />
                  </CollapsibleSection>

                  <GithubDeepDivePanel
                    progress={facts?.github_progress}
                    architectureMaturity={facts?.architecture_maturity}
                  />

                  <LeetcodeInsightsPanel
                    quadrant={facts?.engineering_quadrant}
                    companyReadiness={facts?.company_readiness}
                    topicMastery={facts?.leetcode_topic_mastery}
                  />
                </div>

                <div className="identity-col">
                  <WeeklyBriefCard
                    brief={brief}
                    onRefresh={handleRefreshBrief}
                    loading={briefLoading}
                    error={briefError}
                  />

                  {facts?.architecture_maturity?.maturity_score != null && (
                    <CollapsibleSection title="Architecture Maturity" defaultOpen={false} dense>
                      <div className="identity-maturity">
                        <span className="identity-maturity__score">{facts.architecture_maturity.maturity_score}/100</span>
                        <span className="identity-maturity__label">{facts.architecture_maturity.maturity_label}</span>
                      </div>
                    </CollapsibleSection>
                  )}

                  <GoalsMatchesPanel
                    goals={facts?.active_goals}
                    jobMatches={facts?.recent_job_matches}
                  />

                  <CoverageTimelinePanel
                    coverageGaps={facts?.coverage_gaps}
                    timelineNotes={facts?.timeline_plausibility_notes}
                  />

                  <ClaimFreshnessPanel
                    claimRiskDetails={facts?.claim_risk_details}
                    sourceFreshness={facts?.source_freshness}
                    evidenceCoverage={facts?.evidence_coverage}
                  />

                  <IdentityHistoryPanel history={history} />
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}