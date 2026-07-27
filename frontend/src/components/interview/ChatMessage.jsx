// frontend/src/components/interview/ChatMessage.jsx
import { useState } from 'react'
import { IconCompass } from '../icons/Icons'
import './ChatMessage.css'

function CoachAvatar() {
  return (
    <span className="chat-msg__coach-avatar">
      <IconCompass size={13} />
    </span>
  )
}

function ChatMessage({ message }) {
  const [showShort, setShowShort] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-msg__bubble">{message.text}</div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="chat-msg chat-msg--assistant">
        <div className="chat-msg__bubble chat-msg__bubble--error">{message.message}</div>
      </div>
    )
  }

  // Coach asking a practice question — plain prompt bubble.
  if (message.role === 'coach-prompt') {
    return (
      <div className="chat-msg chat-msg--assistant">
        <div className="chat-msg__prompt-card">
          <div className="chat-msg__coach-row">
            <CoachAvatar />
            <span className="chat-msg__coach-name">Polaris coach</span>
          </div>
          {message.intro && <p className="chat-msg__intro">{message.intro}</p>}
          <p className="chat-msg__question">{message.text}</p>
        </div>
      </div>
    )
  }

  // Full coached answer + notes, returned from the Interview Response Agent.
  const { data } = message

  return (
    <div className="chat-msg chat-msg--assistant">
      <div className="chat-msg__card">
        <div className="chat-msg__coach-row">
          <CoachAvatar />
          <span className="chat-msg__coach-name">Polaris coach</span>
          <span className="chat-msg__label">Model answer &amp; coaching</span>
        </div>

        {data.insufficient_context && (
          <p className="chat-msg__insufficient">
            Not enough context to answer this well{data.context_note ? `: ${data.context_note}` : '.'}
          </p>
        )}

        <p className="chat-msg__answer">{showShort ? data.answer_short : data.answer}</p>

        {data.answer_short && (
          <button type="button" className="chat-msg__toggle" onClick={() => setShowShort((v) => !v)}>
            {showShort ? 'Show full answer' : 'Show short version'}
          </button>
        )}

        {(data.stories_used?.length > 0 || data.competencies?.length > 0) && (
          <div className="chat-msg__pills-row">
            {data.stories_used?.map((s) => (
              <span key={s} className="pill pill--story">{s}</span>
            ))}
            {data.competencies?.map((c) => (
              <span key={c} className="pill pill--competency">{c}</span>
            ))}
          </div>
        )}

        {data.coaching?.length > 0 && (
          <details className="chat-msg__coaching" open>
            <summary>Coaching notes</summary>
            <ul>
              {data.coaching.map((c, i) => (
                <li key={i}><strong>{c.focus}:</strong> {c.note}</li>
              ))}
            </ul>
          </details>
        )}

        {data.follow_up_questions?.length > 0 && (
          <div className="chat-msg__followups">
            <span>Practice a follow-up:</span>
            <div className="chat-msg__chip-row">
              {data.follow_up_questions.map((q, i) => (
                <button key={i} type="button" className="chip" onClick={() => message.onFollowUp?.(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatMessage