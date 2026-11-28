import { useState } from 'react'
import EvidenceList from './EvidenceList'

const MAX_LENGTH = 2000 // the server's limit

const DECIDED = { accepted: 'Accepted', rejected: 'Rejected' }

function shownAs(line) {
  if (line.edited) return 'Your edit'
  if (line.rewrite && line.decision === 'accepted') return 'Suggested wording'
  return 'Your wording'
}

// The AI's rewording beside the original, and what to do about it.
function Suggestion({ line, busy, onChange }) {
  const [confirming, setConfirming] = useState(false)
  const flagged = line.flags.length > 0

  async function accept(confirmed) {
    // Accepting means using the suggestion, so an edit of the user's gives way.
    const change = { decision: 'accepted', confirm_flags: confirmed }
    if (line.edited) change.edited = null
    if (await onChange(change)) setConfirming(false)
  }

  return (
    <div className="tr-suggestion">
      <div className="tr-compare">
        <div>
          <span className="tr-label">Original</span>
          <p>{line.original}</p>
        </div>
        <div>
          <span className="tr-label">Suggested</span>
          <p>{line.rewrite}</p>
        </div>
      </div>

      {flagged ? (
        <div className="tr-flags">
          <strong>Needs your confirmation</strong>
          <ul>
            {line.flags.map((flag) => <li key={flag}>{flag}</li>)}
          </ul>
        </div>
      ) : (
        <p className="tr-clean">
          Your own words: only punctuation, words like “a” and “and”, or how a name or number is written differ.
        </p>
      )}

      {confirming ? (
        <div className="tr-confirm" role="group" aria-label="Confirm this rewording">
          <span>Accept only if the suggestion is true of your work.</span>
          <button type="button" className="tr-btn tr-btn--primary" disabled={busy} onClick={() => accept(true)}>
            It is accurate, use it
          </button>
          <button type="button" className="tr-btn" disabled={busy} onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="tr-actions">
          {line.decision !== 'pending' && (
            <span className={`tr-decision tr-decision--${line.decision}`}>{DECIDED[line.decision]}</span>
          )}
          {(line.decision !== 'accepted' || line.edited) && (
            <button
              type="button"
              className="tr-btn tr-btn--primary"
              disabled={busy}
              onClick={() => (flagged ? setConfirming(true) : accept(false))}
            >
              {line.edited ? 'Use suggestion instead of your edit' : flagged ? 'Accept…' : 'Accept'}
            </button>
          )}
          {line.decision === 'pending' && (
            <button type="button" className="tr-btn" disabled={busy} onClick={() => onChange({ decision: 'rejected' })}>
              Reject
            </button>
          )}
          {line.decision !== 'pending' && (
            <button type="button" className="tr-btn" disabled={busy} onClick={() => onChange({ decision: 'pending' })}>
              Undo
            </button>
          )}
        </div>
      )}
    </div>
  )
}

// One bullet: what the resume says, any suggestion, editing and evidence.
// `onChange` saves a change and resolves to whether it worked.
export default function LineEditor({ line, evidence, busy, error, onChange }) {
  const [draft, setDraft] = useState(null) // text while editing, otherwise null
  const [showEvidence, setShowEvidence] = useState(false)

  async function save() {
    const text = draft.trim()
    if (text === line.text || await onChange({ edited: text || null })) setDraft(null)
  }

  return (
    <li className="tr-line">
      {draft === null ? (
        <div className="tr-line__current">
          <p>{line.text}</p>
          <span className="tr-line__tag">{shownAs(line)}</span>
        </div>
      ) : (
        <div className="tr-editor">
          <textarea
            aria-label="Edit this line"
            value={draft}
            maxLength={MAX_LENGTH}
            rows={3}
            autoFocus
            onChange={(event) => setDraft(event.target.value)}
          />
          <div className="tr-actions">
            <button type="button" className="tr-btn tr-btn--primary" disabled={busy} onClick={save}>Save</button>
            <button type="button" className="tr-btn" disabled={busy} onClick={() => setDraft(null)}>Cancel</button>
          </div>
        </div>
      )}

      {line.rewrite && <Suggestion line={line} busy={busy} onChange={onChange} />}

      {error && <p className="tr-line__error" role="alert">{error}</p>}

      <div className="tr-links">
        {draft === null && (
          <button type="button" onClick={() => setDraft(line.text)}>Edit</button>
        )}
        {line.edited && draft === null && (
          <button type="button" disabled={busy} onClick={() => onChange({ edited: null })}>Remove my edit</button>
        )}
        <button type="button" aria-expanded={showEvidence} onClick={() => setShowEvidence((shown) => !shown)}>
          {showEvidence ? 'Hide evidence' : 'Evidence'}
        </button>
      </div>

      {showEvidence && <EvidenceList sources={line.sources} evidence={evidence} original={line.original} />}
    </li>
  )
}
