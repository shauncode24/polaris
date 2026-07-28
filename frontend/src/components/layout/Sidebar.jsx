import { useState, useCallback, useRef, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useProfileData } from '../../contexts/ProfileDataContext'
import { IconCompass, IconDocument, IconGithub, IconCode, IconTarget, IconChat, IconMic, IconWorkflow } from '../icons/Icons'
import { IconAward, IconRefresh } from '../icons/OnboardingIcons'
import { IconHome, IconSettings, IconHelpCircle, IconPanelLeft, IconSparkle, IconChartBar, IconLock, IconBuilding, IconFolder, IconClipboardList, IconBell } from '../icons/DashboardIcons'
import './Sidebar.css'

const IconGear = (props) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-gear" viewBox="0 0 16 16" {...props}>
    <path d="M8 4.754a3.246 3.246 0 1 0 0 6.492 3.246 3.246 0 0 0 0-6.492M5.754 8a2.246 2.246 0 1 1 4.492 0 2.246 2.246 0 0 1-4.492 0"/>
    <path d="M9.796 1.343c-.527-1.79-3.065-1.79-3.592 0l-.094.319a.873.873 0 0 1-1.255.52l-.292-.16c-1.64-.892-3.433.902-2.54 2.541l.159.292a.873.873 0 0 1-.52 1.255l-.319.094c-1.79.527-1.79 3.065 0 3.592l.319.094a.873.873 0 0 1 .52 1.255l-.16.292c-.892 1.64.901 3.434 2.541 2.54l.292-.159a.873.873 0 0 1 1.255.52l.094.319c.527 1.79 3.065 1.79 3.592 0l.094-.319a.873.873 0 0 1 1.255-.52l.292.16c1.64.893 3.434-.902 2.54-2.541l-.159-.292a.873.873 0 0 1 .52-1.255l.319-.094c1.79-.527 1.79-3.065 0-3.592l-.319-.094a.873.873 0 0 1-.52-1.255l.16-.292c.893-1.64-.902-3.433-2.541-2.54l-.292.159a.873.873 0 0 1-1.255-.52zm-2.633.283c.246-.835 1.428-.835 1.674 0l.094.319a1.873 1.873 0 0 0 2.693 1.115l.291-.16c.764-.415 1.6.42 1.184 1.185l-.159.292a1.873 1.873 0 0 0 1.116 2.692l.318.094c.835.246.835 1.428 0 1.674l-.319.094a1.873 1.873 0 0 0-1.115 2.693l.16.291c.415.764-.42 1.6-1.185 1.184l-.291-.159a1.873 1.873 0 0 0-2.693 1.116l-.094.318c-.246.835-1.428.835-1.674 0l-.094-.319a1.873 1.873 0 0 0-2.692-1.115l-.292.16c-.764.415-1.6-.42-1.184-1.185l.159-.291A1.873 1.873 0 0 0 1.945 8.93l-.319-.094c-.835-.246-.835-1.428 0-1.674l.319-.094A1.873 1.873 0 0 0 3.06 4.377l-.16-.292c-.415-.764.42-1.6 1.185-1.184l.292.159a1.873 1.873 0 0 0 2.692-1.115z"/>
  </svg>
)

// Data-driven nav. `to` = real route (clickable). No `to` + no `locked`/`soon`
// = feature has no page yet, rendered disabled rather than dead-linked.
function useNavGroups() {
  const { results } = useProfileData()

  return [
    {
      label: 'Overview',
      items: [
        { key: 'dashboard', label: 'Dashboard', icon: IconHome, to: '/home' }
      ],
    },
    {
      label: 'Profile',
      items: [
        { key: 'my-profile', label: 'My Profile', icon: IconTarget, to: '/profile' },
        { key: 'resume', label: 'Resume', icon: IconDocument, to: '/resume', badge: results.resume ? 'Synced' : null },
        { key: 'projects-profile', label: 'Projects', icon: IconFolder, to: '/projects' },
        { key: 'github', label: 'GitHub', icon: IconGithub, to: '/build-profile', badge: results.github ? 'Synced' : null },
        { key: 'leetcode', label: 'LeetCode', icon: IconCode, to: '/build-profile', badge: results.leetcode ? 'Synced' : null },
        { key: 'certificates', label: 'Certificates', icon: IconAward, to: '/build-profile' },
        { key: 'notes', label: 'Notes', icon: IconClipboardList },
      ],
    },
    {
      label: 'Applications',
      items: [
        { key: 'app-jobs', label: 'Jobs', icon: IconClipboardList },
        { key: 'app-companies', label: 'Companies', icon: IconBuilding },
      ],
    },
    {
      label: 'Analyze',
      items: [
        { key: 'skill-gap', label: 'Skill Gap Analyzer', icon: IconDocument, to: '/jobs' },
        { key: 'resume-reviewer', label: 'Resume Reviewer', icon: IconRefresh },
        { key: 'project-intel', label: 'Project Intelligence', icon: IconFolder },
        { key: 'company-intel', label: 'Company Intelligence', icon: IconBuilding },
      ],
    },
    {
      label: 'Plan',
      items: [
        { key: 'goals', label: 'Goals', icon: IconTarget, to: '/career-planner' },
        { key: 'career-planner', label: 'Career Planner', icon: IconClipboardList, locked: true },
        { key: 'progress-tracker', label: 'Progress Tracker', icon: IconChartBar },
      ],
    },
    {
      label: 'Interview',
      items: [
        { key: 'interview-agent', label: 'Interview Response Agent', icon: IconChat, to: '/interview' },
        { key: 'mock-interviewer', label: 'Mock Interviewer', icon: IconMic },
        { key: 'interview-readiness', label: 'Interview Readiness Analyzer', icon: IconWorkflow, locked: true },
        { key: 'session-history', label: 'Session History', icon: IconClipboardList },
      ],
    },
    {
      label: 'Coach',
      items: [
        { key: 'nudges', label: 'Nudges', icon: IconBell },
        { key: 'decision-engine', label: 'Decision Engine', icon: IconSparkle, soon: true },
        { key: 'resume-evolution', label: 'Resume Evolution', icon: IconRefresh },
      ],
    },
    {
      label: 'Account',
      items: [
        { key: 'settings', label: 'Settings', icon: IconGear },
        { key: 'help', label: 'Help & Docs', icon: IconHelpCircle },
      ],
    },
  ]
}

function NavItem({ item, isCollapsed }) {
  const Icon = item.icon
  const content = (
    <>
      <Icon size={16} className="sidebar__item-icon" />
      {!isCollapsed && (
        <>
          <span className="sidebar__item-label">{item.label}</span>
          {item.badge && <span className="sidebar__badge sidebar__badge--synced">{item.badge}</span>}
          {item.locked && (
            <span className="sidebar__badge sidebar__badge--locked">
              <IconLock size={10} /> Locked
            </span>
          )}
          {item.soon && <span className="sidebar__badge sidebar__badge--soon">Soon</span>}
        </>
      )}
    </>
  )

  if (item.to) {
    return (
      <NavLink
        to={item.to}
        className={({ isActive }) => `sidebar__item ${isActive ? 'sidebar__item--active' : ''}`}
        end={item.to === '/home'}
        title={isCollapsed ? item.label : undefined}
      >
        {content}
      </NavLink>
    )
  }

  return (
    <span
      className="sidebar__item sidebar__item--disabled"
      title={isCollapsed ? `${item.label} (Coming soon)` : "Coming soon"}
    >
      {content}
    </span>
  )
}

function Sidebar() {
  const { user, logout } = useAuth()
  const groups = useNavGroups()

  const [width, setWidth] = useState(() => {
    const saved = localStorage.getItem('sidebar-width')
    return saved ? parseInt(saved, 10) : 240
  })
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('sidebar-collapsed') === 'true'
  })
  const [collapsedGroups, setCollapsedGroups] = useState(() => {
    const saved = localStorage.getItem('sidebar-collapsed-groups')
    return saved ? JSON.parse(saved) : {}
  })
  const [resizing, setResizing] = useState(false)

  const isResizing = useRef(false)

  const handleMouseMove = useCallback((e) => {
    if (!isResizing.current) return
    let newWidth = e.clientX
    if (newWidth < 120) {
      setIsCollapsed(true)
      localStorage.setItem('sidebar-collapsed', 'true')
    } else {
      setIsCollapsed(false)
      localStorage.setItem('sidebar-collapsed', 'false')
      if (newWidth > 400) newWidth = 400
      setWidth(newWidth)
      localStorage.setItem('sidebar-width', String(newWidth))
    }
  }, [])

  const stopResizing = useCallback(() => {
    isResizing.current = false
    setResizing(false)
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', stopResizing)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }, [handleMouseMove])

  const startResizing = useCallback((e) => {
    isResizing.current = true
    setResizing(true)
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', stopResizing)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [handleMouseMove, stopResizing])

  useEffect(() => {
    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', stopResizing)
    }
  }, [handleMouseMove, stopResizing])

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('sidebar-collapsed', String(next))
      return next
    })
  }

  const toggleGroup = (groupLabel) => {
    setCollapsedGroups((prev) => {
      const next = { ...prev, [groupLabel]: !prev[groupLabel] }
      localStorage.setItem('sidebar-collapsed-groups', JSON.stringify(next))
      return next
    })
  }

  const initials = ((user?.first_name?.[0] || '') + (user?.last_name?.[0] || '')).toUpperCase() || '?'

  return (
    <aside
      className={`sidebar ${isCollapsed ? 'sidebar--collapsed' : ''} ${resizing ? 'sidebar--resizing' : ''}`}
      style={{ width: isCollapsed ? undefined : `${width}px` }}
    >
      <div className="sidebar__brand-row">
        {isCollapsed ? (
          <div className="sidebar__brand-collapsed">
            <span className="sidebar__brand-mark"><IconCompass size={16} /></span>
            <button
              type="button"
              className="sidebar__collapse"
              aria-label="Expand sidebar"
              onClick={toggleCollapse}
            >
              <IconPanelLeft size={15} />
            </button>
          </div>
        ) : (
          <>
            <span className="sidebar__brand">
              <span className="sidebar__brand-mark"><IconCompass size={16} /></span>
              Polaris
            </span>
            <button
              type="button"
              className="sidebar__collapse"
              aria-label="Collapse sidebar"
              onClick={toggleCollapse}
            >
              <IconPanelLeft size={15} />
            </button>
          </>
        )}
      </div>

      <nav className="sidebar__nav">
        {groups.map((group) => {
          const isGroupCollapsed = !isCollapsed && collapsedGroups[group.label]
          return (
            <div className={`sidebar__group ${isGroupCollapsed ? 'sidebar__group--collapsed' : ''}`} key={group.label}>
              <p className="sidebar__group-label" onClick={() => !isCollapsed && toggleGroup(group.label)}>
                <span className="sidebar__group-text">{group.label}</span>
                {!isCollapsed && (
                  <span className="sidebar__group-chevron">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" className="bi bi-chevron-down" viewBox="0 0 16 16">
                      <path fillRule="evenodd" d="M1.646 4.646a.5.5 0 0 1 .708 0L8 10.293l5.646-5.647a.5.5 0 0 1 .708.708l-6 6a.5.5 0 0 1-.708 0l-6-6a.5.5 0 0 1 0-.708"/>
                    </svg>
                  </span>
                )}
              </p>
              <div className="sidebar__group-items">
                {group.items.map((item) => (
                  <NavItem key={item.key} item={item} isCollapsed={isCollapsed} />
                ))}
              </div>
            </div>
          )
        })}
      </nav>

      <div className="sidebar__footer">
        <div
          className="sidebar__user"
          onClick={logout}
          title={isCollapsed ? `Log out (${user?.first_name || 'You'})` : "Log out"}
        >
          <span className="sidebar__user-avatar">{initials}</span>
          {!isCollapsed && (
            <div>
              <span className="sidebar__user-name">{user?.first_name || 'You'}</span>
              <span className="sidebar__user-sub">Career workspace</span>
            </div>
          )}
        </div>
      </div>

      <div className="sidebar__resize-handle" onMouseDown={startResizing} />
    </aside>
  )
}

export default Sidebar