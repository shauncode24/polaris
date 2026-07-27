import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { createGoal } from '../../api/career'
import { IconTarget } from '../icons/Icons'
import StepFooterNav from './StepFooterNav'
import './onboarding-shared.css'

function buildTitle(role, company) {
  if (!role.trim()) return ''
  return company.trim()
    ? `Become a strong ${role.trim()} candidate at ${company.trim()}`
    : `Become a strong ${role.trim()} candidate`
}

function GoalStep({ goal, onSuccess, onContinue, onSkip }) {
  const { token } = useAuth()
  const [role, setRole] = useState(goal?.role || '')
  const [company, setCompany] = useState(goal?.company || '')
  const [date, setDate] = useState(goal?.date || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleContinue() {
    if (!role.trim()) { onSkip(); return }
    setSaving(true)
    setError('')
    try {
      const created = await createGoal(token, {
        title: buildTitle(role, company),
        deadline: date || null,
        priority: null,
        jobDescriptionId: null,
      })
      onSuccess({ role: role.trim(), company: company.trim(), date, goalId: created.id, title: created.title })
      onContinue()
    } catch (err) {
      setError(err.message || 'Could not save this goal — you can set it up later from your dashboard.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <p className="onb-eyebrow">Step 5 of 6 · Your goal</p>
      <h1 className="onb-title">What are you working toward?</h1>
      <p className="onb-lead">
        Tell us your target and we'll seed your first goal — your roadmap, skill gaps, and prep all
        orient around it. Leave it blank and you can set a goal anytime from your dashboard.
      </p>

      {error && <p className="onb-error">{error}</p>}

      <div className="onb-card">
        <div className="onb-field">
          <label>Target role</label>
          <div className="onb-input-icon-wrap">
            <input className="onb-input" placeholder="Senior Frontend Engineer" value={role} onChange={(e) => setRole(e.target.value)} />
            <span className="onb-input-icon"><IconTarget size={16} /></span>
          </div>
        </div>
        <div className="onb-row">
          <div className="onb-field">
            <label>Target company <span className="onb-optional">Optional</span></label>
            <input className="onb-input" placeholder="Any, or a specific one" value={company} onChange={(e) => setCompany(e.target.value)} />
          </div>
          <div className="onb-field">
            <label>Target date <span className="onb-optional">Optional</span></label>
            <input className="onb-input" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
        </div>
      </div>

      <StepFooterNav
        skipLabel="Set this up later"
        onSkip={onSkip}
        loading={saving}
        continueLabel="Continue"
        onContinue={handleContinue}
      />
    </div>
  )
}

export default GoalStep