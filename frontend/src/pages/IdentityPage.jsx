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
import ProfileSnapshotStrip from '../components/identity/ProfileSnapshotStrip'
import RoleFitBars from '../components/identity/RoleFitBars'
import SignalsGapsPanel from '../components/identity/SignalsGapsPanel'
import RecommendedFocusCard from '../components/identity/RecommendedFocusCard'
import IdentityInsights from '../components/identity/IdentityInsights'
import GithubDeepDivePanel from '../components/identity/GithubDeepDivePanel'
import LeetcodeInsightsPanel from '../components/identity/LeetcodeInsightsPanel'
import GoalsMatchesPanel from '../components/identity/GoalsMatchesPanel'
import TechDepthGrid from '../components/identity/TechDepthGrid'
import IdentityEvolution from '../components/identity/IdentityEvolution'
import IdentityHistoryPanel from '../components/identity/IdentityHistoryPanel'
import WeeklyBriefCard from '../components/identity/WeeklyBriefCard'
import PortfolioNarrativePanel from '../components/identity/PortfolioNarrativePanel'
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

              {/* Level 1 — the one conclusion the page exists to deliver */}
              <IdentityHero
                narrative={narrative}
                generatedAt={identity.generated_at}
                degraded={identity.analysis_degraded}
                sourceEvent={identity.source_event}
                isInvalidated={identity.is_invalidated}
                invalidatedReason={identity.invalidated_reason}
                invalidatedAt={identity.invalidated_at}
                sourceFreshness={facts?.source_freshness}
                evidenceCoverage={facts?.evidence_coverage}
                onRefresh={handleRefreshIdentity}
                refreshing={refreshing}
              />

              <ProfileSnapshotStrip facts={facts} />

              {/* Level 2 — the evidence + guidance that actually changes
                  how the user understands themselves */}
              <CollapsibleSection title="Role Fit" defaultOpen={true}>
                <RoleFitBars roleFit={facts?.role_fit} architectureMaturity={facts?.architecture_maturity} />
              </CollapsibleSection>

              <PortfolioNarrativePanel portfolioNarrative={facts?.portfolio_narrative} />

              <SignalsGapsPanel
                strongestSignals={narrative?.strongest_signals}
                biggestGaps={narrative?.biggest_gaps}
              />

              <RecommendedFocusCard text={narrative?.recommended_focus} />

              {/* Level 3 — supporting detail, collapsed by default */}
              <IdentityInsights facts={facts} contradictions={narrative?.contradictions} />

              <GithubDeepDivePanel progress={facts?.github_progress} architectureMaturity={facts?.architecture_maturity} />

              <CollapsibleSection title="Technology Depth" defaultOpen={false}>
                <TechDepthGrid highlights={facts?.technology_depth_highlights} />
              </CollapsibleSection>

              <LeetcodeInsightsPanel
                quadrant={facts?.engineering_quadrant}
                companyReadiness={facts?.company_readiness}
                topicMastery={facts?.leetcode_topic_mastery}
              />

              <GoalsMatchesPanel
                goals={facts?.active_goals}
                jobMatches={facts?.recent_job_matches}
              />

              <WeeklyBriefCard
                brief={brief}
                onRefresh={handleRefreshBrief}
                loading={briefLoading}
                error={briefError}
              />

              {/* Level 4 — history, least important, most compact */}
              {history.length > 1 && (
                <div className="identity-evolution-wrap">
                  <IdentityEvolution
                    history={history}
                    currentNarrative={narrative}
                    currentGeneratedAt={identity.generated_at}
                  />
                </div>
              )}

              <IdentityHistoryPanel history={history} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}