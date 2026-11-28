import { percent } from './labels'

const MARKS = { true: ['✓', 'Covered'], false: ['✗', 'Not covered'], null: ['–', 'Not reviewed'] }

export default function AttemptFeedback({ attempt }) {
  const { feedback, score } = attempt
  return (
    <div className="ik-feedback">
      <p>
        <strong>{score === null ? 'Not scored' : `${percent(score)} of the headings covered`}</strong>
        <span className="ik-hint"> This measures what you covered, not whether it is true or well put.</span>
      </p>
      {feedback.notice && <p className="ik-warning">{feedback.notice}</p>}
      {feedback.warnings.map((warning) => <p key={warning} className="ik-warning">{warning}</p>)}
      {feedback.overall && <p className="ik-fact">{feedback.overall}</p>}
      <ul className="ik-verdicts">
        {feedback.headings.map((heading) => {
          const [mark, meaning] = MARKS[heading.covered]
          return (
            <li key={heading.heading} className={`ik-verdict ik-verdict--${heading.covered}`}>
              <span className="ik-verdict__mark" role="img" aria-label={meaning}>{mark}</span>
              <div>
                <strong>{heading.heading}</strong>
                {heading.quote && <q>{heading.quote}</q>}
                <p>{heading.note || (heading.covered === null ? heading.prompt : '')}</p>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
