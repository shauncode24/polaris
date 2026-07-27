// frontend/src/pages/CareerPlannerPage.jsx
import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import Button from '../components/common/Button'
import { listJobAnalyses } from '../api/jobs'
import { createGoal, listGoals, updateGoal, deleteGoal, generatePlan } from '../api/career'
import GoalSetupPanel from '../components/career/GoalSetupPanel'
import PlanSummaryCard from '../components/career/PlanSummaryCard'
import DailyPlanTimeline from '../components/career/DailyPlanTimeline'
import MilestoneCheckins from '../components/career/MilestoneCheckins'
import TopicSignalsPanel from '../components/career/TopicSignalsPanel'
import GoalManagementPanel from '../components/career/GoalManagementPanel'
import './CareerPlannerPage.css'

function CareerPlannerPage() {
  const { token } = useAuth()
  const [searchParams] = useSearchParams()
  const preselectedJobId = searchParams.get('jobId')

  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(true)
  const [goals, setGoals] = useState([])
  const [goalsLoading, setGoalsLoading] = useState(true)

  const [view, setView] = useState('setup') // 'setup' | 'plan'
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
      .then(async (items) => {
        if (cancelled) return
        setGoals(items)
        // Auto-load the most recent goal's plan on first load, unless the
        // person arrived here specifically to build a roadmap for a job.
        if (items.length > 0 && !preselectedJobId) {
          await loadPlanForGoal(items[0], items)
        } else {
          setView('setup')
        }
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setGoalsLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const loadPlanForGoal = useCallback(async (goal, goalList = goals) => {
    setGenerating(true)
    setError('')
    try {
      const planResponse = await generatePlan(token, goal.id)
      setCurrentGoal(goal)
      setPlan(planResponse)
      setView('plan')
    } catch (err) {
      setError(err.message || 'Could not load the roadmap for this goal.')
    } finally {
      setGenerating(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function handleCreateAndGenerate({ title, deadline, priority, jobDescriptionId }) {
    setGenerating(true)
    setError('')
    try {
      const goal = await createGoal(token, { title, deadline, priority, jobDescriptionId })
      const nextGoals = [goal, ...goals]
      setGoals(nextGoals)
      await loadPlanForGoal(goal, nextGoals)
    } catch (err) {
      setError(err.message || 'Could not generate a roadmap for this goal.')
      setGenerating(false)
    }
  }

  async function handleGenerateExisting(goalId) {
    const goal = goals.find((g) => g.id === goalId)
    if (!goal) return
    await loadPlanForGoal(goal)
  }

  function handleRegenerate() {
    if (currentGoal) loadPlanForGoal(currentGoal)
  }

  async function handleUpdateGoal(goalId, payload) {
    const updated = await updateGoal(token, goalId, payload)
    setGoals((prev) => prev.map((g) => (g.id === goalId ? updated : g)))
    if (currentGoal?.id === goalId) setCurrentGoal(updated)
  }

  async function handleDeleteGoal(goalId) {
    await deleteGoal(token, goalId)
    setGoals((prev) => prev.filter((g) => g.id !== goalId))
    if (currentGoal?.id === goalId) {
      setCurrentGoal(null)
      setPlan(null)
      setView('setup')
    }
  }

  return (
    <div className="career-planner-page">
      <Sidebar />
      <div className="career-planner-page__main">
        <BreadcrumbBar
          section="Plan"
          page="Career Planner"
          actions={
            view === 'plan' && (
              <button type="button" className="career-planner-page__new-goal" onClick={() => setView('setup')}>
                + New goal
              </button>
            )
          }
        />

        <div className="career-planner-page__content">
          {view === 'setup' || !currentGoal ? (
            <>
              <div className="career-planner-page__intro">
                <h1>Career Planner</h1>
                <p>Turn your skill gaps into a structured, day-by-day roadmap.</p>
              </div>

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
            </>
          ) : (
            <>
              {generating && !plan ? (
                <p className="career-planner-page__loading">Building your roadmap…</p>
              ) : plan && (
                <>
                  <PlanSummaryCard goal={currentGoal} plan={plan} onRegenerate={handleRegenerate} busy={generating} />
                  <DailyPlanTimeline dailyPlan={plan.daily_plan} />
                  <MilestoneCheckins checkIns={plan.check_ins} daysAvailable={plan.days_available} />
                  <TopicSignalsPanel topicSignals={plan.topic_signals} />
                </>
              )}
              {error && <p className="career-planner-page__error">{error}</p>}
            </>
          )}

          {!goalsLoading && (
            <GoalManagementPanel
              goals={goals}
              activeGoalId={currentGoal?.id}
              onViewPlan={(goalId) => handleGenerateExisting(goalId)}
              onUpdateGoal={handleUpdateGoal}
              onDeleteGoal={handleDeleteGoal}
              onNewGoal={() => setView('setup')}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default CareerPlannerPage