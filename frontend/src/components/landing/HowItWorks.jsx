import { IconUpload, IconGitBranch, IconWorkflow, IconArrowDown } from '../icons/Icons'
import './HowItWorks.css'

const STEPS = [
  { icon: IconUpload, title: 'Upload Resume', order: '01' },
  { icon: IconGitBranch, title: 'Sync GitHub & LeetCode', order: '02' },
  { icon: IconWorkflow, title: 'Generate Personalized Career Plan', order: '03' },
]

function HowItWorks() {
  return (
    <section className="how-it-works" id="how-it-works">
      <div className="container">
        <p className="eyebrow how-it-works__eyebrow">How it works</p>

        <ol className="how-it-works__steps">
          {STEPS.map(({ icon: Icon, title, order }, index) => (
            <li key={title}>
              <div className="step-card">
                <span className="step-card__icon">
                  <Icon size={18} />
                </span>
                <span className="step-card__title">{title}</span>
                <span className="step-card__order">{order}</span>
              </div>
              {index < STEPS.length - 1 && (
                <div className="how-it-works__connector">
                  <IconArrowDown size={16} />
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}

export default HowItWorks
