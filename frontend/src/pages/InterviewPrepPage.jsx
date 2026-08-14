// frontend/src/pages/InterviewPrepPage.jsx
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import Sidebar from '../components/layout/Sidebar'
import BreadcrumbBar from '../components/layout/BreadcrumbBar'
import { listJobAnalyses } from '../api/jobs'
import {
  askInterviewQuestion,
  correctInterviewResponse,
  getInterviewSessionThread,
  listInterviewSessions,
} from '../api/interview'
import { getEngineeringIdentity } from '../api/identity'
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
  const [searchParams] = useSearchParams()

  const [jobs, setJobs] = useState([])
  const [sessions, setSessions] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [sessionLoadPending, setSessionLoadPending] = useState(false)

  const [targetRole, setTargetRole] = useState('')
  const [targetCompany, setTargetCompany] = useState('')

  const [companyNotes, setCompanyNotes] = useState([])
  const [notesLoading, setNotesLoading] = useState(false)

  const [identityBadges, setIdentityBadges] = useState(null)

  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(false)
  const bottomRef = useRef(null)
  const prefillHandled = useRef(false)

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

  useEffect(() => {
    let cancelled = false
    getEngineeringIdentity(token)
      .then((report) => {
        if (cancelled || !report) return
        const roleFit = report.facts?.role_fit || []
        const topRoleFit = roleFit.length
          ? [...roleFit].sort((a, b) => b.rating - a.rating)[0]
          : null
        setIdentityBadges((prev) => ({ ...prev, topRoleFit }))
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    if (!identityBadges || !targetCompany) return
    getEngineeringIdentity(token)
      .then((report) => {
        if (!report) return
        const readiness = (report.facts?.company_readiness || []).find(
          (c) => c.company.toLowerCase().includes(targetCompany.toLowerCase())
        )
        if (readiness) {
          setIdentityBadges((prev) => ({ ...prev, companyReadiness: readiness }))
        }
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetCompany, token])

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
    setActiveSessionId(null)
    setMessages([
      { id: nextId('coach'), role: 'coach-prompt', text: 'Ask me a question', intro },
    ])
  }

  useEffect(() => {
    if (messages.length === 0) startSession()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const prefill = searchParams.get('prefill')
    if (prefill && !prefillHandled.current) {
      prefillHandled.current = true
      handleSubmitAnswer(prefill)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  function handleNewSession() {
    prefillHandled.current = true
    startSession()
  }

  function askFollowUp(question) {
    handleSubmitAnswer(question)
  }

  function decorateAssistantMessage(response) {
    return {
      id: response.response_id || nextId('assistant'),
      role: 'assistant',
      data: {
        ...response,
        onFollowUp: askFollowUp,
        onCorrect: handleCorrect,
      },
    }
  }

  async function handleSubmitAnswer(questionText) {
    if (!questionText.trim() || pending) return

    setMessages((prev) => [...prev, { id: nextId('user'), role: 'user', text: questionText }])
    setPending(true)

    try {
      const data = await askInterviewQuestion(token, {
        question: questionText,
        targetRole,
        targetCompany,
        sessionId: activeSessionId,
      })
      setActiveSessionId(data.session_id)
      setMessages((prev) => [...prev, decorateAssistantMessage(data)])
      refreshSessions()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId('error'),
          role: 'error',
          message: err.message || 'Something went wrong generating coaching for that answer.',
          error_type: err.error_type || null,
          trace_id: err.trace_id || null,
        },
      ])
    } finally {
      setPending(false)
    }
  }

  async function handleCorrect(originalMessage, correctionText) {
    const parentResponseId = originalMessage.data.response_id
    if (!parentResponseId) return

    setMessages((prev) => [
      ...prev,
      { id: nextId('correction'), role: 'correction-note', text: correctionText },
    ])
    setPending(true)

    try {
      const data = await correctInterviewResponse(token, {
        parentResponseId,
        correction: correctionText,
      })
      setMessages((prev) => [...prev, decorateAssistantMessage(data)])
      refreshSessions()
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: nextId('error'),
          role: 'error',
          message: err.message || 'Something went wrong applying that correction.',
          error_type: err.error_type || null,
          trace_id: err.trace_id || null,
        },
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

  async function handleSelectSession(session) {
    const sessionId = session.session_id || session.id
    if (sessionLoadPending || sessionId === activeSessionId) return

    setSessionLoadPending(true)
    try {
      const thread = await getInterviewSessionThread(token, sessionId)
      const rebuilt = []
      thread.forEach((item) => {
        if (item.correction_of) {
          // The correction's own user-facing "what was wrong" text isn't
          // persisted separately from the regenerated answer, so this
          // just renders as a revised answer with its "Revised" badge —
          // still fully readable, just without replaying the original
          // correction note text.
          rebuilt.push(decorateAssistantMessage(item))
        } else {
          rebuilt.push({ id: nextId('user'), role: 'user', text: item.question })
          rebuilt.push(decorateAssistantMessage(item))
        }
      })
      setMessages(rebuilt)
      setActiveSessionId(sessionId)
      if (session.target_role) setTargetRole(session.target_role)
      if (session.target_company !== undefined) setTargetCompany(session.target_company || '')
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: nextId('error'), role: 'error', message: 'Could not load that session.' },
      ])
    } finally {
      setSessionLoadPending(false)
    }
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
            identityBadges={identityBadges}
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
                activeSessionId={activeSessionId}
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