import { useState } from 'react'
import AnswerOutline from './AnswerOutline'
import PracticePanel from './PracticePanel'
import { percent } from './labels'

const STORY_KINDS = { project: 'Project', experience: 'Experience', leetcode: 'LeetCode' }

// Which of the user's work answers the question, or why none does.
function EvidenceChips({ question }) {
  const { story } = question.outline
  if (question.thin === null) return <span className="ik-chip">Not matched yet</span>
  if (!story) {
    return <span className="ik-chip ik-chip--warning">{question.thin ? 'Thin evidence' : 'Evidence changed'}</span>
  }
  return (
    <>
      <span className="ik-chip ik-chip--evidence">
        {story.kind === 'leetcode' ? story.title : `${STORY_KINDS[story.kind]}: ${story.title}`}
      </span>
      {question.shows.map((shown) => <span key={shown} className="ik-chip">{shown}</span>)}
    </>
  )
}

export default function QuestionCard({ token, question, onPractised }) {
  const [showOutline, setShowOutline] = useState(false)
  // Opened once, then kept, so a half-written answer survives closing it.
  const [practice, setPractice] = useState({ opened: false, open: false })

  return (
    <li className="ik-card ik-question">
      <p className="ik-label">{question.topic}</p>
      <h3>{question.text}</h3>
      <div className="ik-chips">
        <EvidenceChips question={question} />
        {question.attempts > 0 && (
          <span className="ik-chip ik-chip--done">
            {question.latest_score === null ? 'Practised' : `Last score ${percent(question.latest_score)}`}
          </span>
        )}
      </div>
      <div className="ik-actions">
        <button
          type="button"
          className="ik-btn ik-btn--primary"
          aria-expanded={practice.open}
          onClick={() => setPractice(({ open }) => ({ opened: true, open: !open }))}
        >
          {practice.open ? 'Close practice' : 'Practise'}
        </button>
        <button
          type="button"
          className="ik-btn"
          aria-expanded={showOutline}
          onClick={() => setShowOutline((shown) => !shown)}
        >
          {showOutline ? 'Hide outline' : 'Show answer outline'}
        </button>
      </div>
      {showOutline && <AnswerOutline outline={question.outline} />}
      {practice.opened && (
        <div hidden={!practice.open}>
          <PracticePanel token={token} questionId={question.id} onPractised={onPractised} />
        </div>
      )}
    </li>
  )
}
