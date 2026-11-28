import { CATEGORY_LABELS, percent } from './labels'

export default function ProgressSummary({ kit }) {
  const { practised, total, weakest, categories } = kit
  return (
    <section className="ik-card" aria-label="Practice progress">
      <div className="ik-progress__head">
        <strong>{practised} of {total} questions practised</strong>
        {weakest && <span className="ik-hint">Weakest area: {CATEGORY_LABELS[weakest]}</span>}
      </div>
      <div
        className="ik-progress__bar"
        role="progressbar"
        aria-label="Questions practised"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={practised}
      >
        <span style={{ width: `${total ? (practised / total) * 100 : 0}%` }} />
      </div>
      <ul className="ik-progress__categories">
        {categories.map((c) => (
          <li key={c.category}>
            <span>{CATEGORY_LABELS[c.category]}</span>
            <span>
              {c.practised}/{c.total}
              {c.average_score !== null && `, ${percent(c.average_score)} average`}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
