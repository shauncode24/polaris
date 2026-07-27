import { useNavigate } from 'react-router-dom'
import Card from '../common/Card'
import { IconUpload, IconGitBranch, IconCode, IconBriefcase, IconTarget, IconChat } from '../icons/Icons'
import './QuickActionsBar.css'

function QuickActionsBar() {
  const navigate = useNavigate()

  const actions = [
    { label: 'Upload resume', icon: IconUpload, onClick: () => navigate('/build-profile') },
    { label: 'Sync GitHub', icon: IconGitBranch, onClick: () => navigate('/build-profile') },
    { label: 'Sync LeetCode', icon: IconCode, onClick: () => navigate('/build-profile') },
    { label: 'Analyze a job', icon: IconBriefcase, onClick: () => navigate('/jobs') },
    { label: 'Set or edit goal', icon: IconTarget, onClick: () => navigate('/career-planner') },
    { label: 'Ask an interview question', icon: IconChat, onClick: () => navigate('/interview') },
  ]

  return (
    <Card className="quick-actions">
      <h3 className="quick-actions__title">Quick actions</h3>
      <div className="quick-actions__grid">
        {actions.map(({ label, icon: Icon, onClick }) => (
          <button type="button" key={label} className="quick-actions__item" onClick={onClick}>
            <Icon size={15} />
            {label}
          </button>
        ))}
      </div>
    </Card>
  )
}

export default QuickActionsBar