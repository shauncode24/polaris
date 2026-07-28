import { useNavigate } from 'react-router-dom'
import InfoCard from '../common/InfoCard'
import { IconSparkle } from '../icons/DashboardIcons'
import './ProjectIntelligencePanel.css'

function buildPrompt(action, projectName) {
  const subject = projectName ? ` about ${projectName}` : ''
  switch (action) {
    case 'explain_2min':
      return `Explain${subject} in 2 minutes, like you're pitching it in an interview.`
    case 'google':
      return `Walk me through${subject} the way you would in a Google interview.`
    case 'amazon':
      return `Walk me through${subject} the way you would in an Amazon interview, focused on ownership and impact.`
    case 'architecture':
      return `Explain the architecture${subject} in technical depth.`
    case 'star':
      return `Give me a STAR-structured answer${subject}.`
    case 'followups':
      return `What follow-up questions would an interviewer likely ask${subject}?`
    default:
      return `Tell me about${subject}.`
  }
}

const ACTIONS = [
  { key: 'explain_2min', label: 'Explain in 2 minutes' },
  { key: 'google', label: 'Google interview' },
  { key: 'amazon', label: 'Amazon interview' },
  { key: 'architecture', label: 'Explain architecture' },
  { key: 'star', label: 'Generate STAR answer' },
  { key: 'followups', label: 'Follow-up questions' },
]

function ProjectIntelligencePanel({ featuredProjectName }) {
  const navigate = useNavigate()

  function handleClick(actionKey) {
    const prompt = buildPrompt(actionKey, featuredProjectName)
    navigate(`/interview?prefill=${encodeURIComponent(prompt)}`)
  }

  return (
    <InfoCard icon={IconSparkle} iconTone="accent" title="Project intelligence">
      <p className="project-intel-panel__lead">Practice the engineering story behind your work.</p>
      <div className="project-intel-panel__chips">
        {ACTIONS.map((action) => (
          <button
            key={action.key}
            type="button"
            className="project-intel-panel__chip"
            onClick={() => handleClick(action.key)}
          >
            {action.label}
          </button>
        ))}
      </div>
    </InfoCard>
  )
}

export default ProjectIntelligencePanel