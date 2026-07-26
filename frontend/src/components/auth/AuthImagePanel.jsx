import { Link } from 'react-router-dom'
import { IconCompass, IconArrowRight } from '../icons/Icons'
import './AuthImagePanel.css'

function AuthImagePanel() {
  return (
    <aside className="auth-image">
      <div className="auth-image__top">
        <span className="auth-image__brand">
          <IconCompass size={20} />
          Polaris
        </span>
        <Link to="/" className="auth-image__back">
          Back to website <IconArrowRight size={14} />
        </Link>
      </div>

      <div className="auth-image__caption">
        <p>Navigate your career,</p>
        <p className="auth-image__caption-script">one goal at a time.</p>
      </div>

      <div className="auth-image__dots" aria-hidden="true">
        <span /><span /><span className="auth-image__dot--active" />
      </div>
    </aside>
  )
}

export default AuthImagePanel