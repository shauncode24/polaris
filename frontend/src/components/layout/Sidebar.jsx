import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { useProfileData } from '../../contexts/ProfileDataContext'
import { IconCompass, IconDocument, IconGithub, IconCode, IconTarget, IconChat, IconMic, IconWorkflow } from '../icons/Icons'
import { IconAward, IconRefresh } from '../icons/OnboardingIcons'
import { IconHome, IconSettings, IconHelpCircle, IconPanelLeft, IconSparkle, IconChartBar, IconLock, IconBuilding, IconFolder, IconClipboardList, IconBell } from '../icons/DashboardIcons'
import './Sidebar.css'

// Data-driven nav. `to` = real route (clickable). No `to` + no `locked`/`soon`
// = feature has no page yet, rendered disabled rather than dead-linked.
function useNavGroups() {
  const { results } = useProfileData()

  return [
    {
      label: 'Overview',
      items: [{ key: 'dashboard', label: 'Dashboard', icon: IconHome, to: '/home' }],
    },
    {
      label: 'Profile',
      items: [
        { key: 'my-profile', label: 'My Profile', icon: IconTarget, to: '/profile' },
        { key: 'resume', label: 'Resume', icon: IconDocument, to: '/build-profile', badge: results.resume ? 'Synced' : null },
        { key: 'github', label: 'GitHub Sync', icon: IconGithub, to: '/build-profile', badge: results.github ? 'Synced' : null },
        { key: 'leetcode', label: 'LeetCode Sync', icon: IconCode, to: '/build-profile', badge: results.leetcode ? 'Synced' : null },
        { key: 'certificates', label: 'Certificates', icon: IconAward, to: '/build-profile' },
        { key: 'notes', label: 'Notes', icon: IconClipboardList },
      ],
    },
    {
      label: 'Analyze',
      items: [
        { key: 'skill-gap', label: 'Skill Gap Analyzer', icon: IconDocument, to: '/jobs' },
        { key: 'resume-reviewer', label: 'Resume Reviewer', icon: IconRefresh },
        { key: 'company-intel', label: 'Company Intelligence', icon: IconBuilding },
        { key: 'project-intel', label: 'Project Intelligence', icon: IconFolder },
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
      label: 'Interview Prep',
      items: [
        { key: 'interview-agent', label: 'Interview Response Agent', icon: IconChat, to: '/interview' },
        { key: 'mock-interviewer', label: 'Mock Interviewer', icon: IconMic },
        { key: 'interview-readiness', label: 'Interview Readiness', icon: IconWorkflow, locked: true },
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
  ]
}

function NavItem({ item }) {
  const Icon = item.icon
  const content = (
    <>
      <Icon size={16} className="sidebar__item-icon" />
      <span className="sidebar__item-label">{item.label}</span>
      {item.badge && <span className="sidebar__badge sidebar__badge--synced">{item.badge}</span>}
      {item.locked && (
        <span className="sidebar__badge sidebar__badge--locked">
          <IconLock size={10} /> Locked
        </span>
      )}
      {item.soon && <span className="sidebar__badge sidebar__badge--soon">Soon</span>}
    </>
  )

  if (item.to) {
    return (
      <NavLink to={item.to} className={({ isActive }) => `sidebar__item ${isActive ? 'sidebar__item--active' : ''}`} end={item.to === '/home'}>
        {content}
      </NavLink>
    )
  }

  return (
    <span className="sidebar__item sidebar__item--disabled" title="Coming soon">
      {content}
    </span>
  )
}

function Sidebar() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const { results } = useProfileData()
  const groups = useNavGroups()
  const hasGoal = Boolean(results.goal)

  const initials = ((user?.first_name?.[0] || '') + (user?.last_name?.[0] || '')).toUpperCase() || '?'

  return (
    <aside className="sidebar">
      <div className="sidebar__brand-row">
        <span className="sidebar__brand">
          <span className="sidebar__brand-mark"><IconCompass size={16} /></span>
          Polaris
        </span>
        <button type="button" className="sidebar__collapse" aria-label="Collapse sidebar">
          <IconPanelLeft size={15} />
        </button>
      </div>

      {!hasGoal && (
        <button type="button" className="sidebar__goal-cta" onClick={() => navigate('/career-planner')}>
          <span className="sidebar__goal-cta-icon"><IconTarget size={15} /></span>
          <span>
            <span className="sidebar__goal-cta-title">Set your first goal</span>
            <span className="sidebar__goal-cta-sub">Unlock your roadmap</span>
          </span>
        </button>
      )}

      <nav className="sidebar__nav">
        {groups.map((group) => (
          <div className="sidebar__group" key={group.label}>
            <p className="sidebar__group-label">{group.label}</p>
            <div className="sidebar__group-items">
              {group.items.map((item) => <NavItem key={item.key} item={item} />)}
            </div>
          </div>
        ))}
      </nav>

      <div className="sidebar__footer">
        <button type="button" className="sidebar__footer-link">
          <IconSettings size={16} /> Settings
        </button>
        <button type="button" className="sidebar__footer-link">
          <IconHelpCircle size={16} /> Help &amp; docs
        </button>
        <div className="sidebar__user" onClick={logout} title="Log out">
          <span className="sidebar__user-avatar">{initials}</span>
          <div>
            <span className="sidebar__user-name">{user?.first_name || 'You'}</span>
            <span className="sidebar__user-sub">Career workspace</span>
          </div>
        </div>
      </div>
    </aside>
  )
}

export default Sidebar