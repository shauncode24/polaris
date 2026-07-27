// frontend/src/components/layout/BreadcrumbBar.jsx
import { useAuth } from '../../contexts/AuthContext'
import ThemeToggle from '../auth/ThemeToggle'
import './BreadcrumbBar.css'

function BreadcrumbBar({ section, page, actions }) {
  const { user } = useAuth()
  const initials = ((user?.first_name?.[0] || '') + (user?.last_name?.[0] || '')).toUpperCase() || '?'

  return (
    <header className="breadcrumb-bar">
      <div className="breadcrumb-bar__text">
        <span className="breadcrumb-bar__parent">Polaris / {section}</span>
        <span className="breadcrumb-bar__current">{page}</span>
      </div>
      <div className="breadcrumb-bar__actions">
        {actions}
        <ThemeToggle />
        <span className="breadcrumb-bar__avatar">{initials}</span>
      </div>
    </header>
  )
}

export default BreadcrumbBar