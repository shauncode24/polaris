import { Link } from 'react-router-dom'
import './StickyActionBar.css'

function StickyActionBar({ roleLabel, jobId }) {
  return (
    <div className="sticky-action-bar">
      <p className="sticky-action-bar__text">
        Ready to act on this analysis for <strong>{roleLabel || 'this role'}</strong>?
      </p>
      <div className="sticky-action-bar__actions">
        <Link
          to={jobId ? `/career-planner?jobId=${jobId}` : '/career-planner'}
          className="sticky-action-bar__btn sticky-action-bar__btn--primary"
        >
          Generate Career Roadmap →
        </Link>
        <Link to="/interview" className="sticky-action-bar__btn sticky-action-bar__btn--outline">
          Practice interview questions →
        </Link>
      </div>
    </div>
  )
}

export default StickyActionBar