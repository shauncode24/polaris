import Button from '../common/Button'
import { IconArrowRight } from '../icons/Icons'

function StepFooterNav({ skipLabel = 'Skip this step', onSkip, continueLabel = 'Continue', onContinue, loading, disabled }) {
  return (
    <div className="onb-footer">
      {onSkip ? (
        <button type="button" className="onb-footer__skip" onClick={onSkip}>{skipLabel}</button>
      ) : <span />}
      <Button
        variant="primary"
        onClick={onContinue}
        disabled={disabled || loading}
        icon={!loading ? <IconArrowRight size={16} /> : null}
      >
        {loading ? 'Working…' : continueLabel}
      </Button>
    </div>
  )
}

export default StepFooterNav