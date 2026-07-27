import { useAuth } from '../../contexts/AuthContext'
import ThemeToggle from '../auth/ThemeToggle'
import { IconSearch, IconBell } from '../icons/DashboardIcons'
import './TopBar.css'

function TopBar({
  section = 'Overview',
  page = 'Dashboard',
  notificationCount = 0,
  hideSearch = false,
  hideNotifications = false,
  actions = null,
}) {
  const { user } = useAuth()
  const initials = ((user?.first_name?.[0] || '') + (user?.last_name?.[0] || '')).toUpperCase() || '?'

  return (
    <header className="topbar">
      <div className="topbar__breadcrumb">
        <span className="topbar__breadcrumb-parent">Polaris / {section}</span>
        <span className="topbar__breadcrumb-current">{page}</span>
      </div>

      <div className="topbar__actions">
        {actions}

        {!hideSearch && (
          <label className="topbar__search">
            <IconSearch size={15} />
            <input type="text" placeholder="Search your workspace…" />
          </label>
        )}

        {!hideNotifications && (
          <button type="button" className="topbar__icon-btn" aria-label="Notifications">
            <IconBell size={17} />
            {notificationCount > 0 && <span className="topbar__badge">{notificationCount}</span>}
          </button>
        )}

        <ThemeToggle />

        <span className="topbar__avatar">{initials}</span>
      </div>
    </header>
  )
}

export default TopBar