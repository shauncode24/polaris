import { useState } from 'react'
import './ChatMessage.css'

function ChatMessage({ message }) {
  const [showShort, setShowShort] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-msg__bubble">{message.question}</div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="chat-msg chat-msg--error">
        <div className="chat-msg__bubble">{message.message}</div>
      </div>
    )
  }

  const { data } = message

  return (
    <div className="chat-msg chat-msg--assistant">
      <div className="chat-msg__card">
        <span className="chat-msg__label">Coached answer</span>

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
            <span>You might also be asked:</span>
            <ul>
              {data.follow_up_questions.map((q, i) => <li key={i}>{q}</li>)}
            </ul>
          </div>
        )}

        {data.blueprint_used && (
          <p className="chat-msg__meta">{data.question_type} · {data.blueprint_used}</p>
        )}
      </div>
    </div>
  )
}

export default ChatMessage