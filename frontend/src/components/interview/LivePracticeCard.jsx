// frontend/src/components/interview/LivePracticeCard.jsx
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import './LivePracticeCard.css'

function LivePracticeCard({ targetRole, targetCompany, messages, pending, onSubmitAnswer, bottomRef }) {
  return (
    <section className="live-practice">
      <div className="live-practice__header">
        <div>
          <h2>Live practice</h2>
          <p>{targetRole ? `${targetRole}${targetCompany ? ` · ${targetCompany}` : ''}` : 'General practice'}</p>
        </div>
        <span className="live-practice__badge">
          <span className="live-practice__badge-dot" /> Coaching on
        </span>
      </div>

      <div className="live-practice__conversation">
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {pending && <div className="live-practice__typing">Coaching your answer…</div>}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSubmit={onSubmitAnswer} disabled={pending} placeholder="Ask an interview question..." />
    </section>
  )
}

export default LivePracticeCard