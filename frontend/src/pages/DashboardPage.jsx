import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { listJobAnalyses } from '../api/jobs'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import Button from '../components/common/Button'
import InfoCard from '../components/common/InfoCard'
import EmptyState from '../components/common/EmptyState'
import ProfileCompletionCard from '../components/dashboard/ProfileCompletionCard'
import StatCard from '../components/dashboard/StatCard'
import DecisionEngineCard from '../components/dashboard/DecisionEngineCard'
import SkillConfidenceCard from '../components/dashboard/SkillConfidenceCard'
import ProgressTrackerCard from '../components/dashboard/ProgressTrackerCard'
import NudgesCard from '../components/dashboard/NudgesCard'
import QuickActionsBar from '../components/dashboard/QuickActionsBar'
import ProjectIntelligenceCard from '../components/dashboard/ProjectIntelligenceCard'
import { IconBriefcase, IconTarget, IconFlag, IconChat, IconWorkflow } from '../components/icons/Icons'
import './DashboardPage.css'

function DashboardPage() {
  const navigate = useNavigate()
  const { token, user } = useAuth()
  const { results } = useProfileData()

  const [jobAnalyses, setJobAnalyses] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    listJobAnalyses(token)
      .then((items) => { if (!cancelled) setJobAnalyses(items) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setJobsLoading(false) })
    return () => { cancelled = true }
  }, [token])

  const skillsProcessed = results.resume?.skills_processed
  const skillsHigh = results.resume?.skills_high_confidence
  const skillsMedium = results.resume?.skills_medium_confidence
  const skillsLow = results.resume?.skills_low_confidence

  const projectsCreated = results.resume?.projects_created
  const reposSynced = results.github?.summary?.repos_synced
  const experiencesCreated = results.resume?.experiences_created
  const educationCreated = results.resume?.education_created

  // Heuristic readiness: latest analyzed job's overall match %, until a
  // real /readiness endpoint exists.
  const latestAnalysis = jobAnalyses[0]
  const readiness = latestAnalysis?.overall_match_percentage

  const resumeProjects = (results.github?.repositories || [])
    .slice()
    .sort((a, b) => (b.project_score?.overall || 0) - (a.project_score?.overall || 0))
    .slice(0, 2)
    .map((r) => ({ name: r.name, description: r.description || 'No description synced yet.' }))

  return (
    <div className="dashboard-layout">
      <Sidebar />
      <div className="dashboard-main">
        <TopBar section="Overview" page="Dashboard" notificationCount={1} />

        <div className="dashboard-content">
          <div className="dashboard-hero">
            <div>
              <p className="dashboard-hero__welcome">Welcome back, {user?.first_name || 'You'}</p>
              <h1 className="dashboard-hero__title">Your career, at a glance.</h1>
            </div>
            <div className="dashboard-hero__actions">
              <Button variant="outline" icon={<IconBriefcase size={16} />} onClick={() => navigate('/jobs')}>
                Analyze a job
              </Button>
              <Button variant="primary" icon={<IconTarget size={16} />} onClick={() => navigate('/career-planner')}>
                Set a goal
              </Button>
            </div>
          </div>

          <ProfileCompletionCard />

          <div className="dashboard-stats-grid">
            <StatCard
              icon={IconTarget}
              label="Skills tracked"
              value={skillsProcessed ?? '—'}
              subLabel={skillsProcessed != null ? `${skillsHigh ?? 0} high · ${skillsMedium ?? 0} medium · ${skillsLow ?? 0} low` : 'Upload a resume to start tracking'}
            />
            <StatCard
              icon={IconWorkflow}
              label="Projects"
              value={projectsCreated ?? '—'}
              subLabel={reposSynced != null ? `${reposSynced} repos synced` : 'No GitHub sync yet'}
            />
            <StatCard
              icon={IconFlag}
              label="Experience"
              value={experiencesCreated ?? '—'}
              subLabel={educationCreated != null ? `${educationCreated} education record${educationCreated === 1 ? '' : 's'}` : 'From your resume'}
            />
            <StatCard
              icon={IconChat}
              label="Readiness score"
              value={readiness != null ? `${Math.round(readiness)}%` : '—'}
              subLabel={readiness != null ? latestAnalysis.role || 'Latest job analysis' : 'Set a goal, then analyze a job'}
            />
          </div>

          <div className="dashboard-columns">
            <div className="dashboard-col dashboard-col--main">
              <InfoCard icon={IconTarget} iconTone="accent" title="Active goal">
                <EmptyState
                  message="No active goal yet — set one to unlock your roadmap."
                  ctaLabel="Set a goal"
                  onCta={() => navigate('/career-planner')}
                />
              </InfoCard>

              <InfoCard icon={IconWorkflow} iconTone="accent" title="Today's focus" badge={<span className="dashboard-subtitle">From your Career Planner</span>}>
                <EmptyState
                  message="No active plan generated yet — set a goal to shape your first day."
                  ctaLabel="Open planner"
                  onCta={() => navigate('/career-planner')}
                />
              </InfoCard>

              <SkillConfidenceCard />
              <ProgressTrackerCard />
            </div>

            <div className="dashboard-col dashboard-col--side">
              <DecisionEngineCard />
              <NudgesCard />

              <InfoCard icon={IconBriefcase} iconTone="accent" title="Recent job analyses">
                {jobsLoading ? (
                  <p className="dashboard-side-loading">Loading…</p>
                ) : jobAnalyses.length === 0 ? (
                  <EmptyState message="No jobs analyzed yet." ctaLabel="Analyze a new job" onCta={() => navigate('/jobs')} />
                ) : (
                  <ul className="dashboard-recent-jobs">
                    {jobAnalyses.slice(0, 3).map((j) => (
                      <li key={j.id} onClick={() => navigate(`/jobs`)}>
                        <span>{j.role || 'Untitled role'}{j.company ? ` · ${j.company}` : ''}</span>
                        {j.overall_match_percentage != null && <strong>{Math.round(j.overall_match_percentage)}%</strong>}
                      </li>
                    ))}
                  </ul>
                )}
              </InfoCard>

              <InfoCard icon={IconWorkflow} iconTone="accent" title="Resume health">
                <EmptyState message="Run your first resume review to get a score and one highest-leverage fix." ctaLabel="View full resume review" />
              </InfoCard>

              <InfoCard icon={IconChat} iconTone="accent" title="Interview prep">
                <EmptyState message="You haven't practiced any questions yet." ctaLabel="Continue practicing" onCta={() => navigate('/interview')} />
              </InfoCard>
            </div>
          </div>

          <QuickActionsBar />
          <ProjectIntelligenceCard projects={resumeProjects} />
        </div>
      </div>
    </div>
  )
}

export default DashboardPage