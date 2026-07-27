import { useNavigate } from 'react-router-dom'
import Card from '../common/Card'
import { useProfileCompletion } from '../../hooks/useProfileCompletion'
import { IconCheck } from '../icons/OnboardingIcons'
import { IconArrowRight } from '../icons/Icons'
import './ProfileCompletionCard.css'

function ProfileCompletionCard() {
  const navigate = useNavigate()
  const { checklist, percent, nextStep, totalSteps } = useProfileCompletion()

  return (
    <Card className="completion-card">
      <div className="completion-card__header">
        <div>
          <div className="completion-card__title-row">
            <h3>Complete your profile</h3>
            <span className="completion-card__pct-badge">{percent}</span>
          </div>
          <p className="completion-card__lead">Every connected source improves how Polaris matches, plans, and prepares you.</p>
        </div>
        <button type="button" className="completion-card__continue" onClick={() => navigate('/build-profile')}>
          Continue · Step {nextStep} of {totalSteps} <IconArrowRight size={14} />
        </button>
      </div>

      <div className="completion-card__bar">
        <div className="completion-card__bar-fill" style={{ width: `${percent}%` }} />
      </div>

      <div className="completion-card__checklist">
        {checklist.map((step) => (
          <div className="completion-card__step" key={step.key}>
            <span className={`completion-card__step-mark ${step.done ? 'is-done' : ''}`}>
              {step.done ? <IconCheck size={12} /> : null}
            </span>
            <div>
              <span className="completion-card__step-label">{step.label}</span>
              <span className="completion-card__step-sub">{step.subLabel}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default ProfileCompletionCard