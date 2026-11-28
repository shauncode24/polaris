import { useState } from 'react'

const PARTS = {
  parsing: 'Readable by screening software',
  completeness: 'Sections and detail',
  content_quality: 'Bullet writing',
  structure: 'Order and dates',
  keywords: 'Common technical terms',
  professionalism: 'Contact details and consistency',
}
// What "Edit contact details" can fix.
const CONTACT_WARNINGS = new Set(['missing_phone', 'missing_linkedin'])

function Change({ from, to }) {
  const difference = to - from
  if (difference === 0) return <span className="tr-change">no change</span>
  const direction = difference > 0 ? 'up' : 'down'
  return <span className={`tr-change tr-change--${direction}`}>{difference > 0 ? '+' : '−'}{Math.abs(difference)}</span>
}

// One measure, for the uploaded resume (if any) and the tailored one.
function Measure({ label, before, after, show }) {
  const compared = before != null
  return (
    <div className="tr-measure">
      <span className="tr-label">{label}</span>
      <p>
        {compared && <><span className="tr-measure__before">{show(before)}</span> → </>}
        <strong>{show(after)}</strong>
        {compared && <Change from={before} to={after} />}
      </p>
    </div>
  )
}

function Keywords({ title, words, tone }) {
  if (words.length === 0) return null
  return (
    <div className="tr-keywords">
      <span>{title}</span>
      {words.map((word) => <span key={word} className={`tr-keyword tr-keyword--${tone}`}>{word}</span>)}
    </div>
  )
}

function KeywordDetail({ before, after }) {
  if (!before) {
    return (
      <>
        <Keywords title="Covered:" words={after.matched} tone="good" />
        <Keywords title="Missing:" words={after.missing} tone="plain" />
      </>
    )
  }
  const had = new Set(before.matched)
  const has = new Set(after.matched)
  return (
    <>
      <Keywords title="Gained:" words={after.matched.filter((word) => !had.has(word))} tone="good" />
      <Keywords title="Lost:" words={before.matched.filter((word) => !has.has(word))} tone="bad" />
      <Keywords title="In both:" words={after.matched.filter((word) => had.has(word))} tone="plain" />
      <Keywords title="Not in the tailored resume:" words={after.missing.filter((word) => !had.has(word))} tone="plain" />
    </>
  )
}

export default function ScorePanel({ score }) {
  const [showChecks, setShowChecks] = useState(false)
  const { before, after, uploaded } = score

  return (
    <section className="tr-card tr-score" aria-label="Score">
      <div className="tr-score__measures">
        {after.keywords && (
          <Measure
            label="Job keywords covered"
            before={before?.keywords?.matched.length}
            after={after.keywords.matched.length}
            show={(count) => `${count} of ${after.keywords.total}`}
          />
        )}
        <Measure label="ATS checks" before={before?.ats_score} after={after.ats_score} show={(value) => `${value}/100`} />
      </div>

      <p className="tr-hint">
        {before
          ? `Compared with your uploaded resume${uploaded.filename ? ` (${uploaded.filename})` : ''}.`
          : 'Upload your resume to compare this one with it.'}
        {' '}Suggestions count once you accept them.
      </p>

      {after.keywords
        ? <KeywordDetail before={before?.keywords} after={after.keywords} />
        : <p className="tr-hint">This job lists no required skills, so keywords can’t be checked.</p>}

      <div className="tr-links">
        <button type="button" aria-expanded={showChecks} onClick={() => setShowChecks((shown) => !shown)}>
          {showChecks ? 'Hide checks' : `Show checks (${after.warnings.length} to fix on this resume)`}
        </button>
      </div>

      {showChecks && (
        <div className="tr-checks">
          <table>
            <thead>
              <tr>
                <th scope="col">Check (out of 100)</th>
                {before && <th scope="col">Uploaded</th>}
                <th scope="col">Tailored</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(PARTS).map(([key, label]) => (
                <tr key={key}>
                  <th scope="row">{label}</th>
                  {before && <td>{before.parts[key]}</td>}
                  <td>{after.parts[key]}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {after.warnings.length > 0 && (
            <ul>
              {after.warnings.map((warning) => <li key={warning.type}>{warning.detail}</li>)}
            </ul>
          )}
          {after.warnings.some((warning) => CONTACT_WARNINGS.has(warning.type)) && (
            <p className="tr-hint">Add them with “Edit contact details” under your name.</p>
          )}
          <p className="tr-hint">These are automated rules that approximate screening software, not a real one.</p>
        </div>
      )}
    </section>
  )
}
