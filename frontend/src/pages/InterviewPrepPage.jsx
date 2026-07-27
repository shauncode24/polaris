import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { IconCompass } from '../components/icons/Icons'
import ThemeToggle from '../components/auth/ThemeToggle'
import { askInterviewQuestion } from '../api/interview'
import InterviewSetupBar from '../components/interview/InterviewSetupBar'
import ChatMessage from '../components/interview/ChatMessage'
import ChatInput from '../components/interview/ChatInput'
import InterviewSidebar from '../components/interview/InterviewSidebar'
import './InterviewPrepPage.css'

const STARTER_QUESTIONS = [
  'Tell me about yourself',
  'Why should we hire you?',
  'What is your biggest weakness?',
  'Tell me about a project you are proud of',
  'Why this role?',
  'Tell me about a challenge you faced',
]

function InterviewPrepPage() {
  const { token } = useAuth()
  const [targetRole, setTargetRole] = useState('')
  const [targetCompany, setTargetCompany] = useState('')
  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pending])

  async function handleAsk(question) {
    const trimmed = question.trim()
    if (!trimmed || pending) return

    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, role: 'user', question: trimmed }])
    setPending(true)

    try {
      const data = await askInterviewQuestion(token, {
        question: trimmed,
        targetRole: targetRole.trim(),
        targetCompany: targetCompany.trim(),
      })
      setMessages((prev) => [
        ...prev,
        { id: data.response_id || `a-${Date.now()}`, role: 'assistant', data },
      ])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: 'error', message: err.message || 'Something went wrong generating that answer.' },
      ])
    } finally {
      setPending(false)
    }
  }

  const questionsAsked = messages.filter((m) => m.role === 'user').length

  const storiesUsed = new Set()
  const competencies = new Set()
  messages.forEach((m) => {
    if (m.role === 'assistant') {
      ;(m.data.stories_used || []).forEach((s) => storiesUsed.add(s))
      ;(m.data.competencies || []).forEach((c) => competencies.add(c))
    }
  })

  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  const followUps = !pending ? lastAssistant?.data?.follow_up_questions || [] : []

  return (
    <div className="interview-page">
      <header className="interview-page__header">
        <span className="interview-page__brand">
          <IconCompass size={18} /> Polaris
        </span>
        <ThemeToggle />
      </header>

      <div className="interview-page__body">
        <main className="interview-page__main">
          <div className="interview-page__intro">
            <h1>Interview Prep</h1>
            <p>Ask an interview question and get a coached answer built from your real resume, projects, and skills.</p>
          </div>

          <InterviewSetupBar
            targetRole={targetRole}
            targetCompany={targetCompany}
            onChangeRole={setTargetRole}
            onChangeCompany={setTargetCompany}
          />

          <div className="interview-page__conversation">
            {messages.length === 0 && (
              <div className="interview-page__welcome">
                <p>👋 Ready when you are. Pick a question below, or type your own.</p>
                <div className="interview-page__chips">
                  {STARTER_QUESTIONS.map((q) => (
                    <button key={q} type="button" className="chip" onClick={() => handleAsk(q)}>
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}

            {pending && <div className="interview-page__typing">Thinking through your profile…</div>}

            <div ref={bottomRef} />
          </div>

          {followUps.length > 0 && (
            <div className="interview-page__followups">
              <span>Continue with:</span>
              <div className="interview-page__chips">
                {followUps.map((q) => (
                  <button key={q} type="button" className="chip" onClick={() => handleAsk(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          <ChatInput onSubmit={handleAsk} disabled={pending} />
        </main>

        <InterviewSidebar
          targetRole={targetRole}
          targetCompany={targetCompany}
          questionsAsked={questionsAsked}
          storiesUsed={[...storiesUsed]}
          competencies={[...competencies]}
        />
      </div>
    </div>
  )
}

export default InterviewPrepPage