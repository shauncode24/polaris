import { IconDocument, IconGithub, IconCode, IconUser } from '../icons/Icons'
import { IconClose } from '../icons/OnboardingIcons'
import Button from '../common/Button'
import ThemeToggle from '../auth/ThemeToggle'
import { IconCompass, IconArrowRight } from '../icons/Icons'
import '../../components/onboarding/onboarding-shared.css'
import './WelcomeStep.css'

const SOURCES = [
  { icon: IconDocument, title: 'Resume', sub: 'Experience & skills' },
  { icon: IconGithub, title: 'GitHub', sub: 'Real project evidence' },
  { icon: IconCode, title: 'LeetCode', sub: 'Problem-solving signal' },
]

function WelcomeStep({ onStart, onSaveExit }) {
  return (
    <div className="onb-page">
      <header className="onb-header">
        <span className="onb-header__brand"><IconCompass size={18} /> Polaris</span>
        <div className="onb-header__actions">
          <button type="button" className="onb-header__save" onClick={onSaveExit}>
            <IconClose size={14} /> Save &amp; exit
          </button>
          <ThemeToggle />
        </div>
      </header>

      <div className="onb-content welcome-step">
        <p className="onb-eyebrow">Welcome to Polaris</p>
        <h1 className="onb-title">Let's build your profile</h1>
        <p className="onb-lead">
          Your profile powers everything else — skill gap analysis, job matching, career
          roadmaps, and interview prep. The more evidence we gather now, the sharper every
          recommendation gets.
        </p>

        <div className="onb-card welcome-step__diagram">
          <div className="welcome-step__sources">
            {SOURCES.map(({ icon: Icon, title, sub }) => (
              <div className="welcome-step__source" key={title}>
                <span className="welcome-step__source-icon"><Icon size={18} /></span>
                <span className="welcome-step__source-title">{title}</span>
                <span className="welcome-step__source-sub">{sub}</span>
              </div>
            ))}
          </div>
          <div className="welcome-step__profile-pill">
            <IconUser size={16} /> Your career profile
          </div>
        </div>

        <div className="welcome-step__actions">
          <span className="welcome-step__time-note">
            🕐 Takes about 5 minutes — you can skip most steps and finish later.
          </span>
          <Button variant="primary" onClick={onStart} icon={<IconArrowRight size={16} />}>
            Get started
          </Button>
        </div>
      </div>
    </div>
  )
}

export default WelcomeStep