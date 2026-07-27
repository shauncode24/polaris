import { useSimulatedSteps } from '../../hooks/useSimulatedSteps'
import { IconCheck } from '../icons/OnboardingIcons'
import './SimulatedProgressList.css'

function SimulatedProgressList({ title, steps, running }) {
  const activeIndex = useSimulatedSteps(steps, running)

  return (
    <div className="sim-progress">
      {title && <p className="sim-progress__title">{title}</p>}
      <ul className="sim-progress__list">
        {steps.map((label, i) => {
          const state = i < activeIndex ? 'done' : i === activeIndex ? 'active' : 'pending'
          return (
            <li key={label} className={`sim-progress__item sim-progress__item--${state}`}>
              <span className="sim-progress__icon">
                {state === 'done' && <IconCheck size={13} />}
                {state === 'active' && <span className="sim-progress__spinner" />}
                {state === 'pending' && <span className="sim-progress__dot" />}
              </span>
              <span className="sim-progress__label">
                {label}
                {state === 'done' && <em>(complete)</em>}
                {state === 'active' && <em>(in progress)</em>}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export default SimulatedProgressList