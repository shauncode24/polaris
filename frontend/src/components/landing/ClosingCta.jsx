import Button from '../common/Button'
import { IconArrowRight } from '../icons/Icons'
import './ClosingCta.css'

function ClosingCta() {
  return (
    <section className="closing-cta" id="login">
      <div className="container closing-cta__inner">
        <h2 className="closing-cta__title">
          One profile. One roadmap.
          <span className="closing-cta__title-script">One AI coach.</span>
        </h2>

        <Button as="a" href="#top" variant="primary" icon={<IconArrowRight size={16} />}>
          Enter Polaris
        </Button>
      </div>
    </section>
  )
}

export default ClosingCta
