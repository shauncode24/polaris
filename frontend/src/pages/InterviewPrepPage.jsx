// frontend/src/pages/InterviewPrepPage.jsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import { listJobAnalyses } from '../api/jobs'
import { askInterviewQuestion, listInterviewSessions } from '../api/interview'
import { listCompanyNotes, createCompanyNote } from '../api/companyNotes'
import TargetInterviewBar from '../components/interview/TargetInterviewBar'
import LivePracticeCard from '../components/interview/LivePracticeCard'
import PastSessionsPanel from '../components/interview/PastSessionsPanel'
import CompanyNotesPanel from '../components/interview/CompanyNotesPanel'
import './InterviewPrepPage.css'

const OPENER_QUESTIONS = [
  'Tell me about a service or project you owned end-to-end. What changed because you were responsible for it?',
  'Walk me through a recent piece of work you are proud of, and why it mattered.',
  'Tell me about yourself.',
]

let idCounter = 0
function nextId(prefix) {
  idCounter += 1
  return `${prefix}-${idCounter}`
}

function InterviewPrepPage() {
  const { token } = useAuth()

  const [jobs, setJobs] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [activeSessionId, setActiveSessionId] = useState(null)

  const [targetRole, setTargetRole] = useState('')
  const [targetCompany, setTargetCompany] = useState('')

  const [companyNotes, setCompanyNotes] = useState([])
  const [notesLoading, setNotesLoading] = useState(false)

  const [messages, setMessages] = useState([])
  const [currentQuestion, setCurrentQuestion] = useState('')
  const [pending, setPending] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pending])

  useEffect(() => {
    let cancelled = false
    listJobAnalyses(token)
      .then((items) => {
        if (cancelled) return
        setJobs(items)
        if (items.length > 0 && !targetRole) {
          setTargetRole(items[0].role || '')
          setTargetCompany(items[0].company || '')
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  function refreshSessions() {
    setSessionsLoading(true)
    listInterviewSessions(token)
      .then(setSessions)
      .catch(() => {})
      .finally(() => setSessionsLoading(false))
  }

  useEffect(() => {
    refreshSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  useEffect(() => {
    if (!targetCompany) {
      setCompanyNotes([])
      return
    }
    let cancelled = false
    setNotesLoading(true)
    listCompanyNotes(token, targetCompany)
      .then((items) => { if (!cancelled) setCompanyNotes(items) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setNotesLoading(false) })
    return () => { cancelled = true }
  }, [token, targetCompany])

  const opener = useMemo(() => {
    if (targetRole) {
      return `Tell me about a service or project you owned end-to-end at a ${targetRole} level. What changed because you were responsible for it?`
    }
    return OPENER_QUESTIONS[0]
  }, [targetRole])

  function startSession(intro) {
    setMessages([
      { id: nextId('coach'), role: 'coach-prompt', text: opener, intro },
    ])
    setCurrentQuestion(opener)
  }

  useEffect(() => {
    if (messages.length === 0) startSession()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleNewSession() {
    startSession()
  }

  function askFollowUp(question) {
    setMessages((prev) => [...prev, { id: nextId('coach'), role: 'coach-prompt', text: question }])
    setCurrentQuestion(question)
  }

  async function handleSubmitAnswer(answerText) {
    const questionAsked = currentQuestion || opener

    setMessages((prev) => [...prev, { id: nextId('user'), role: 'user', text: answerText }])
    setPending(true)

    try {
      const data = await askInterviewQuestion(token, {
        question: questionAsked,
        targetRole,
        targetCompany,
      })
      setMessages((prev) => [
        ...prev,
        { id: data.response_id || nextId('assistant'), role: 'assistant', data: { ...data, onFollowUp: askFollowUp } },
      ])
      refreshSessions()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: nextId('error'), role: 'error', message: err.message || 'Something went wrong generating coaching for that answer.' },
      ])
    } finally {
      setPending(false)
    }
  }

  function handleSelectJob(job) {
    setTargetRole(job.role || '')
    setTargetCompany(job.company || '')
  }

  function handleManualTarget(role, company) {
    setTargetRole(role)
    setTargetCompany(company)
  }

  async function handleAddCompanyNote(content) {
    const note = await createCompanyNote(token, { company: targetCompany, content })
    setCompanyNotes((prev) => [note, ...prev])
  }

  function handleSelectSession(session) {
    setActiveSessionId(session.id)
    if (session.target_role) setTargetRole(session.target_role)
    if (session.target_company !== undefined) setTargetCompany(session.target_company || '')
  }

  return (
    <div className="interview-page">
      <Sidebar />
      <div className="interview-page__main">
        <BreadcrumbBar
          section="Interview Prep"
          page="Interview Response Agent"
          actions={
            <button type="button" className="interview-page__new-session" onClick={handleNewSession}>
              ↻ New session
            </button>
          }
        />

        <div className="interview-page__content">
          <div className="interview-page__intro">
            <h1>Interview Response Agent</h1>
            <p>Practice your answer, then get grounded coaching on the parts that matter.</p>
          </div>

          <TargetInterviewBar
            targetRole={targetRole}
            targetCompany={targetCompany}
            jobs={jobs}
            onSelectJob={handleSelectJob}
            onManualChange={handleManualTarget}
          />

          <div className="interview-page__columns">
            <LivePracticeCard
              targetRole={targetRole}
              targetCompany={targetCompany}
              messages={messages}
              pending={pending}
              onSubmitAnswer={handleSubmitAnswer}
              bottomRef={bottomRef}
            />

            <div className="interview-page__side">
              <PastSessionsPanel
                sessions={sessions}
                loading={sessionsLoading}
                activeId={activeSessionId}
                onSelect={handleSelectSession}
              />
              <CompanyNotesPanel
                company={targetCompany}
                notes={companyNotes}
                loading={notesLoading}
                onAdd={handleAddCompanyNote}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InterviewPrepPage