// frontend/src/components/career/GoalSetupPanel.jsx
import { useEffect, useState } from 'react'
import Button from '../common/Button'
import './GoalSetupPanel.css'

const PRIORITIES = ['High', 'Medium', 'Low']

function buildTitle({ source, role, company, selectedJob }) {
  if (source === 'job' && selectedJob) {
    const r = selectedJob.role || 'this role'
    return selectedJob.company
      ? `Become a strong ${r} candidate at ${selectedJob.company}`
      : `Become a strong ${r} candidate`
  }
  if (role.trim()) {
    return company.trim()
      ? `Become a strong ${role.trim()} candidate at ${company.trim()}`
      : `Become a strong ${role.trim()} candidate`
  }
  return ''
}

function GoalSetupPanel({
  jobs, jobsLoading, goals, goalsLoading, preselectedJobId,
  onCreateAndGenerate, onGenerateExisting, busy,
}) {
  const [tab, setTab] = useState('new') // 'new' | 'existing'
  const [source, setSource] = useState('job') // 'job' | 'manual'
  const [selectedJobId, setSelectedJobId] = useState('')
  const [role, setRole] = useState('')
  const [company, setCompany] = useState('')
  const [deadline, setDeadline] = useState('')
  const [priority, setPriority] = useState('')
  const [title, setTitle] = useState('')
  const [titleTouched, setTitleTouched] = useState(false)
  const [selectedGoalId, setSelectedGoalId] = useState('')
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (preselectedJobId && jobs.some((j) => j.id === preselectedJobId)) {
      setSource('job')
      setSelectedJobId(preselectedJobId)
    }
  }, [preselectedJobId, jobs])

  const selectedJob = jobs.find((j) => j.id === selectedJobId) || null

  useEffect(() => {
    if (titleTouched) return
    setTitle(buildTitle({ source, role, company, selectedJob }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, role, company, selectedJobId])

  function handleSubmitNew(e) {
    e.preventDefault()
    setFormError('')
    if (source === 'job' && !selectedJobId) {
      setFormError('Select an analyzed job, or switch to manual entry.')
      return
    }
    if (source === 'manual' && !role.trim()) {
      setFormError('Enter a target role.')
      return
    }
    if (!title.trim()) {
      setFormError('Give this goal a title.')
      return
    }
    onCreateAndGenerate({
      title: title.trim(),
      deadline: deadline || null,
      priority: priority || null,
      jobDescriptionId: source === 'job' ? selectedJobId : null,
    })
  }

  function handleSubmitExisting(e) {
    e.preventDefault()
    setFormError('')
    if (!selectedGoalId) {
      setFormError('Select an existing goal.')
      return
    }
    onGenerateExisting(selectedGoalId)
  }

  return (
    <div className="goal-panel">
      <div className="goal-panel__header">
        <h2 className="goal-panel__heading">Choose what you're working toward</h2>
        <p className="goal-panel__subheading">A focused goal becomes a day-by-day plan you can act on.</p>
      </div>

      <div className="goal-panel__tabs" role="tablist">
        <button
          type="button" role="tab" aria-selected={tab === 'new'}
          className={`goal-panel__tab ${tab === 'new' ? 'goal-panel__tab--active' : ''}`}
          onClick={() => setTab('new')}
        >
          New goal
        </button>
        <button
          type="button" role="tab" aria-selected={tab === 'existing'}
          className={`goal-panel__tab ${tab === 'existing' ? 'goal-panel__tab--active' : ''}`}
          onClick={() => setTab('existing')}
        >
          Existing goal
        </button>
      </div>

      {tab === 'new' ? (
        <form className="goal-panel__form" onSubmit={handleSubmitNew}>
          <div className="goal-panel__mode-toggle" role="tablist">
            <button
              type="button"
              className={`goal-panel__mode-btn ${source === 'job' ? 'goal-panel__mode-btn--active' : ''}`}
              onClick={() => setSource('job')}
            >
              From analyzed job
            </button>
            <button
              type="button"
              className={`goal-panel__mode-btn ${source === 'manual' ? 'goal-panel__mode-btn--active' : ''}`}
              onClick={() => setSource('manual')}
            >
              Manual entry
            </button>
          </div>

          {source === 'job' ? (
            jobsLoading ? (
              <p className="goal-panel__hint">Loading your analyzed jobs…</p>
            ) : jobs.length === 0 ? (
              <p className="goal-panel__hint">
                You haven't analyzed a job yet — switch to manual entry, or <a href="/jobs">analyze one first</a>.
              </p>
            ) : (
              <label className="goal-panel__field">
                Analyzed job
                <select value={selectedJobId} onChange={(e) => setSelectedJobId(e.target.value)}>
                  <option value="">Select an analyzed job…</option>
                  {jobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {j.role || 'Untitled role'}{j.company ? ` · ${j.company}` : ''}
                      {j.overall_match_percentage != null ? ` · ${Math.round(j.overall_match_percentage)}% match` : ''}
                    </option>
                  ))}
                </select>
                <span className="goal-panel__field-hint">Your roadmap will prioritize this job's actual missing skills.</span>
              </label>
            )
          ) : (
            <div className="goal-panel__row">
              <label className="goal-panel__field">
                Target role
                <input type="text" value={role} onChange={(e) => setRole(e.target.value)} placeholder="e.g. Data Engineer" />
              </label>
              <label className="goal-panel__field">
                Company <span className="goal-panel__optional">optional</span>
                <input type="text" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Optional" />
              </label>
            </div>
          )}

          <label className="goal-panel__field">
            Goal title
            <input
              type="text"
              value={title}
              onChange={(e) => { setTitle(e.target.value); setTitleTouched(true) }}
              placeholder="Auto-suggested from your source"
            />
          </label>

          <div className="goal-panel__row">
            <label className="goal-panel__field">
              Target date <span className="goal-panel__optional">optional</span>
              <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
            </label>
            <label className="goal-panel__field">
              Priority <span className="goal-panel__optional">optional</span>
              <select value={priority} onChange={(e) => setPriority(e.target.value)}>
                <option value="">None</option>
                {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </label>
          </div>

          {formError && <p className="goal-panel__error">{formError}</p>}

          <div className="goal-panel__submit-row">
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? 'Generating…' : 'Generate roadmap →'}
            </Button>
          </div>
        </form>
      ) : (
        <form className="goal-panel__form" onSubmit={handleSubmitExisting}>
          {goalsLoading ? (
            <p className="goal-panel__hint">Loading your goals…</p>
          ) : goals.length === 0 ? (
            <p className="goal-panel__hint">No goals yet — create a new one instead.</p>
          ) : (
            <label className="goal-panel__field">
              Existing goal
              <select value={selectedGoalId} onChange={(e) => setSelectedGoalId(e.target.value)}>
                <option value="">Select a goal…</option>
                {goals.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.title}{g.deadline ? ` · due ${g.deadline}` : ''}
                  </option>
                ))}
              </select>
            </label>
          )}

          {formError && <p className="goal-panel__error">{formError}</p>}

          <div className="goal-panel__submit-row">
            <Button type="submit" variant="primary" disabled={busy}>
              {busy ? 'Generating…' : 'Generate roadmap →'}
            </Button>
          </div>
        </form>
      )}
    </div>
  )
}

export default GoalSetupPanel