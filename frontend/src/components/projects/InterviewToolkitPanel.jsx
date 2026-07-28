import { useNavigate } from 'react-router-dom'
import InfoCard from '../common/InfoCard'
import { IconSparkle } from '../icons/DashboardIcons'
import './InterviewToolkitPanel.css'

function buildPrompt(action, projectName) {
  const subject = projectName ? ` about ${projectName}` : ''
  switch (action) {
    case 'explain_simply':
      return `Explain${subject} in plain terms, like you're describing it to a non-technical person.`
    case 'technical_deep_dive':
      return `Give me a technical deep dive${subject}, including the hardest engineering decision you made.`
    case 'architecture_review':
      return `Walk me through the architecture${subject} — strengths, weaknesses, and what you'd improve given more time.`
    case 'behavioral_stories':
      return `What behavioral stories (ownership, conflict, failure) does${subject.replace('about', '')} let me tell?`
    case 'recruiter_questions':
      return `What would a recruiter ask${subject} in a 20-second skim of my resume?`
    case 'system_design':
      return `Turn${subject} into a system design interview question and answer it the way you built it.`
    default:
      return `Tell me about${subject}.`
  }
}

const ACTIONS = [
  { key: 'explain_simply', label: 'Explain Simply' },
  { key: 'technical_deep_dive', label: 'Technical Deep Dive' },
  { key: 'architecture_review', label: 'Architecture Review' },
  { key: 'behavioral_stories', label: 'Behavioral Stories' },
  { key: 'recruiter_questions', label: 'Recruiter Questions' },
  { key: 'system_design', label: 'System Design Questions' },
]

function InterviewToolkitPanel({ featuredProjectName }) {
  const navigate = useNavigate()

  function handleClick(actionKey) {
    const prompt = buildPrompt(actionKey, featuredProjectName)
    navigate(`/interview?prefill=${encodeURIComponent(prompt)}`)
  }

  return (
    <InfoCard icon={IconSparkle} iconTone="accent" title="Interview Toolkit">
      <p className="interview-toolkit__lead">
        One consistent set of angles for turning{featuredProjectName ? ` ${featuredProjectName}` : ' your strongest project'} into rehearsed answers.
      </p>
      <div className="interview-toolkit__grid">
        {ACTIONS.map((action) => (
          <button
            key={action.key}
            type="button"
            className="interview-toolkit__chip"
            onClick={() => handleClick(action.key)}
          >
            {action.label}
          </button>
        ))}
      </div>
    </InfoCard>
  )
}

export default InterviewToolkitPanel