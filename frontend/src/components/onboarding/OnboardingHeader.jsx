import { IconCompass } from '../icons/Icons'
import { IconClose, IconChevronLeft } from '../icons/OnboardingIcons'
import ThemeToggle from '../auth/ThemeToggle'
import './OnboardingHeader.css'

const TOTAL_STEPS = 6

function OnboardingHeader({ step, stepLabel, onBack, onSaveExit }) {
  return (
    <>
      <header className="onb-header">
        <span className="onb-header__brand">
          <IconCompass size={18} /> Polaris
        </span>

        {step > 0 && (
          <div className="onb-header__center">
            <span className="onb-header__step-label">
              Step {step} of {TOTAL_STEPS}{stepLabel ? ` · ${stepLabel}` : ''}
            </span>
            <div className="onb-progress">
              {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
                <span key={i} className={`onb-progress__seg ${i < step ? 'onb-progress__seg--filled' : ''}`} />
              ))}
            </div>
          </div>
        )}

        <div className="onb-header__actions">
          <button type="button" className="onb-header__save" onClick={onSaveExit}>
            <IconClose size={14} /> Save &amp; exit
          </button>
          <ThemeToggle />
        </div>
      </header>

      {onBack && (
        <div className="onb-back-row">
          <button type="button" className="onb-back" onClick={onBack}>
            <IconChevronLeft size={14} /> Back
          </button>
        </div>
      )}
    </>
  )
}

export default OnboardingHeader