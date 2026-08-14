// frontend/src/components/interview/ChatMessage.jsx
import { useState } from 'react'
import { IconCompass } from '../icons/Icons'
import CorrectionInput from './CorrectionInput'
import './ChatMessage.css'

function CoachAvatar() {
  return (
    <span className="chat-msg__coach-avatar">
      <IconCompass size={13} />
    </span>
  )
}

/**
 * GroundingBadge — surfaces ALL three grounding fields the backend now populates:
 *   grounding.unverifiable_claims       — numeric/story claims not found verbatim in profile
 *   grounding.possible_fabricated_entities — placeholder/invented entity names caught post-prose
 *   grounding.uses_flagged_project      — answer references a project with an open Claim Audit
 *
 * Implementation plan §P: these three fields MUST be user-visible, not silently dropped.
 * Previously only unverifiable_claims and uses_flagged_project were rendered;
 * possible_fabricated_entities was completely absent.
 */
function GroundingBadge({ grounding }) {
  if (!grounding) return null
  const {
    unverifiable_claims: claims = [],
    possible_fabricated_entities: fabricated = [],
    uses_flagged_project: flagged = false,
  } = grounding

  const totalIssues = claims.length + fabricated.length
  if (totalIssues === 0 && !flagged) return null

  const summaryText = (() => {
    const parts = []
    if (fabricated.length > 0) parts.push(`${fabricated.length} possible invented name${fabricated.length > 1 ? 's' : ''}`)
    if (claims.length > 0) parts.push(`${claims.length} claim${claims.length > 1 ? 's' : ''} to verify`)
    if (flagged) parts.push('flagged project')
    return parts.join(' · ')
  })()

  return (
    <details className="chat-msg__grounding">
      <summary>
        ⚠ {summaryText}
      </summary>
      <div className="chat-msg__grounding-body">
        {fabricated.length > 0 && (
          <>
            <p className="chat-msg__grounding-section-title">Possible invented names</p>
            <p className="chat-msg__grounding-desc">
              These names weren't found in your real profile — they may be hallucinated. Do not
              use this answer as-is if any of these are wrong:
            </p>
            <ul>
              {fabricated.map((f, i) => <li key={i}><code>{f}</code></li>)}
            </ul>
          </>
        )}
        {claims.length > 0 && (
          <>
            <p className="chat-msg__grounding-section-title">Claims to double-check</p>
            <p className="chat-msg__grounding-desc">
              These weren't found verbatim in your profile data — verify before using them:
            </p>
            <ul>
              {claims.map((c, i) => <li key={i}>{c}</li>)}
            </ul>
          </>
        )}
        {flagged && (
          <p className="chat-msg__grounding-flag">
            ⚑ This answer references a project with an unresolved Claim Audit finding — see the
            Projects page.
          </p>
        )}
      </div>
    </details>
  )
}

/**
 * ClaimsVerificationBadge — surfaces claims_needing_verification, which is the
 * plan stage's own honest list of statements resting on thin evidence.
 * Implementation plan §P: this field must be rendered, not silently dropped.
 *
 * Distinct from grounding (which is deterministic post-hoc checking) — this is the
 * model's own self-reported uncertainty from the planning stage, before prose runs.
 */
function ClaimsVerificationBadge({ claims }) {
  if (!claims || claims.length === 0) return null
  return (
    <details className="chat-msg__claims-verify">
      <summary>
        ℹ {claims.length} claim{claims.length > 1 ? 's' : ''} to add evidence for
      </summary>
      <div className="chat-msg__claims-verify-body">
        <p>
          The coach flagged these statements as resting on thin evidence. Consider adding more
          detail to your profile (metrics, specifics) to strengthen this answer:
        </p>
        <ul>
          {claims.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
      </div>
    </details>
  )
}

/**
 * InsufficientContextNote — renders a differentiated message based on
 * insufficient_context_reason, which the backend now populates with one of
 * three distinct values: "empty_profile", "model_declined", "grounding_rejected".
 * Implementation plan §S: each failure class must produce a distinguishable response.
 */
function InsufficientContextNote({ insufficient_context, insufficient_context_reason, context_note }) {
  if (!insufficient_context) return null

  const reasonMessages = {
    empty_profile: {
      title: 'No profile data found',
      detail: 'Upload a resume or add experiences and projects to get personalised answers.',
    },
    grounding_rejected: {
      title: 'Couldn\'t build a grounded answer',
      detail:
        'After two attempts, the coach couldn\'t produce an answer that cites only real facts from your profile. '
        + 'This usually means the question needs more relevant experience added to your profile.',
    },
    model_declined: {
      title: 'Not enough context for this question',
      detail: context_note || 'Add more relevant experiences or projects to answer this well.',
    },
  }

  const resolved = reasonMessages[insufficient_context_reason] || {
    title: 'Not enough context',
    detail: context_note || '',
  }

  const modifierClass = insufficient_context_reason === 'grounding_rejected'
    ? 'chat-msg__insufficient--grounding'
    : insufficient_context_reason === 'empty_profile'
      ? 'chat-msg__insufficient--empty'
      : ''

  return (
    <div className={`chat-msg__insufficient ${modifierClass}`}>
      <strong>{resolved.title}</strong>
      {resolved.detail && <p>{resolved.detail}</p>}
    </div>
  )
}

/**
 * AutoAttachedJobBadge — shown when the backend auto-attached a job context
 * from the user's active goal because no explicit job_intelligence_id was passed.
 * Implementation plan §M: frontend must signal this rather than letting JD context
 * silently appear with no explanation.
 */
function AutoAttachedJobBadge({ jobId }) {
  if (!jobId) return null
  return (
    <div className="chat-msg__auto-job">
      <span className="chat-msg__auto-job-icon">⚙</span>
      Using context from your active goal's job description
    </div>
  )
}

function ChatMessage({ message }) {
  const [showShort, setShowShort] = useState(false)
  const [correcting, setCorrecting] = useState(false)

  if (message.role === 'user') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-msg__bubble">{message.text}</div>
      </div>
    )
  }

  if (message.role === 'correction-note') {
    return (
      <div className="chat-msg chat-msg--user">
        <div className="chat-msg__bubble chat-msg__bubble--correction">
          <span className="chat-msg__correction-tag">Correction</span>
          {message.text}
        </div>
      </div>
    )
  }

  if (message.role === 'error') {
    // Structured 502 errors from the backend now carry error_type + trace_id
    const isGroundingDegraded = message.error_type === 'generation_degraded'
    return (
      <div className="chat-msg chat-msg--assistant">
        <div className="chat-msg__bubble chat-msg__bubble--error">
          {isGroundingDegraded
            ? 'The coaching service hit a temporary issue. Try again in a moment.'
            : (message.message || 'Something went wrong generating coaching for that answer.')}
          {message.trace_id && (
            <span className="chat-msg__trace-id">ref: {message.trace_id.slice(0, 8)}</span>
          )}
        </div>
      </div>
    )
  }

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

  const { data } = message

  function handleCorrectionSubmit(correctionText) {
    setCorrecting(false)
    message.onCorrect?.(message, correctionText)
  }

  return (
    <div className="chat-msg chat-msg--assistant">
      <div className="chat-msg__card">
        <div className="chat-msg__coach-row">
          <CoachAvatar />
          <span className="chat-msg__coach-name">Polaris coach</span>
          <span className="chat-msg__label">Model answer &amp; coaching</span>
          {data.correction_of && <span className="chat-msg__correction-badge">Revised</span>}
        </div>

        {/* §M — auto-attached JD context notice */}
        <AutoAttachedJobBadge jobId={data.auto_attached_job_intelligence_id} />

        {/* §S — differentiated insufficient_context rendering */}
        <InsufficientContextNote
          insufficient_context={data.insufficient_context}
          insufficient_context_reason={data.insufficient_context_reason}
          context_note={data.context_note}
        />

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

        {/* §H — grounding badge: now includes possible_fabricated_entities */}
        <GroundingBadge grounding={data.grounding} />

        {/* §P — claims_needing_verification: was completely absent before */}
        <ClaimsVerificationBadge claims={data.claims_needing_verification} />

        {data.suggested_action && (
          <div className="chat-msg__suggested-action">
            <strong>Worth knowing:</strong> {data.suggested_action}
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

        {!data.insufficient_context && (
          correcting ? (
            <CorrectionInput
              onSubmit={handleCorrectionSubmit}
              onCancel={() => setCorrecting(false)}
              pending={message.correctionPending}
            />
          ) : (
            <button type="button" className="chat-msg__correct-btn" onClick={() => setCorrecting(true)}>
              That's not quite right
            </button>
          )
        )}
      </div>
    </div>
  )
}

export default ChatMessage