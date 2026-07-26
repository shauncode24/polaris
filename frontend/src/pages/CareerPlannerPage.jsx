import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { IconCompass } from '../components/icons/Icons'
import ThemeToggle from '../components/auth/ThemeToggle'
import { listJobAnalyses } from '../api/jobs'
import { createGoal, listGoals, generatePlan } from '../api/career'
import GoalSetupPanel from '../components/career/GoalSetupPanel'
import PlanSummaryCard from '../components/career/PlanSummaryCard'
import DailyPlanTimeline from '../components/career/DailyPlanTimeline'
import TopicSignalsPanel from '../components/career/TopicSignalsPanel'
import './CareerPlannerPage.css'

function CareerPlannerPage() {
  const { token } = useAuth()
  const [searchParams] = useSearchParams()
  const preselectedJobId = searchParams.get('jobId')

  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [goals, setGoals] = useState([])
  const [goalsLoading, setGoalsLoading] = useState(true)

  const [currentGoal, setCurrentGoal] = useState(null)
  const [plan, setPlan] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    listJobAnalyses(token)
      .then((items) => { if (!cancelled) setJobs(items) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setJobsLoading(false) })
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    let cancelled = false
    listGoals(token)
      .then((items) => { if (!cancelled) setGoals(items) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setGoalsLoading(false) })
    return () => { cancelled = true }
  }, [token])

  async function handleCreateAndGenerate({ title, deadline, priority, jobDescriptionId }) {
    setGenerating(true)
    setError('')
    try {
      const goal = await createGoal(token, { title, deadline, priority, jobDescriptionId })
      setGoals((prev) => [goal, ...prev])
      const planResponse = await generatePlan(token, goal.id)
      setCurrentGoal(goal)
      setPlan(planResponse)
    } catch (err) {
      setError(err.message || 'Could not generate a roadmap for this goal.')
    } finally {
      setGenerating(false)
    }
  }

  async function handleGenerateExisting(goalId) {
    const goal = goals.find((g) => g.id === goalId)
    if (!goal) return
    setGenerating(true)
    setError('')
    try {
      const planResponse = await generatePlan(token, goalId)
      setCurrentGoal(goal)
      setPlan(planResponse)
    } catch (err) {
      setError(err.message || 'Could not generate a roadmap for this goal.')
    } finally {
      setGenerating(false)
    }
  }

  function handleRegenerate() {
    if (currentGoal) handleGenerateExisting(currentGoal.id)
  }

  return (
    <div className="career-planner-page">
      <header className="career-planner-page__header">
        <span className="career-planner-page__brand">
          <IconCompass size={18} /> Polaris
        </span>
        <ThemeToggle />
      </header>

      <main className="career-planner-page__main">
        <h1>Career Planner</h1>
        <p className="career-planner-page__lead">
          Turn your skill gaps into a structured, day-by-day roadmap toward your target role.
        </p>

        <GoalSetupPanel
          jobs={jobs}
          jobsLoading={jobsLoading}
          goals={goals}
          goalsLoading={goalsLoading}
          preselectedJobId={preselectedJobId}
          onCreateAndGenerate={handleCreateAndGenerate}
          onGenerateExisting={handleGenerateExisting}
          busy={generating}
        />

        {error && <p className="career-planner-page__error">{error}</p>}
        {generating && !plan && <p className="career-planner-page__loading">Building your roadmap…</p>}

        {plan && currentGoal && (
          <>
            <PlanSummaryCard goal={currentGoal} plan={plan} onRegenerate={handleRegenerate} busy={generating} />
            <DailyPlanTimeline dailyPlan={plan.daily_plan} checkIns={plan.check_ins} daysAvailable={plan.days_available} />
            <TopicSignalsPanel topicSignals={plan.topic_signals} />
          </>
        )}
      </main>
    </div>
  )
}

export default CareerPlannerPage