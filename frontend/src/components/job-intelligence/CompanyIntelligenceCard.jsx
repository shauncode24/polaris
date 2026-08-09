// frontend/src/components/job-intelligence/CompanyIntelligenceCard.jsx
import './CompanyIntelligenceCard.css'

const SIGNAL_LABELS = {
  culture: 'Culture',
  values: 'Values',
  work_environment: 'Work environment',
  learning_development: 'Learning & development',
  diversity_inclusion: 'Diversity & inclusion',
  recognition: 'Recognition',
}

function CompanyIntelligenceCard({ company }) {
  const signals = company?.company_signals || {}
  const hasSignalCategories = Object.values(signals).some((arr) => arr?.length > 0)
  const hasSignal =
    company &&
    (company.industry ||
      company.products_mentioned?.length ||
      company.technologies_mentioned?.length ||
      company.engineering_hints?.length ||
      hasSignalCategories)

  if (!hasSignal) {
    return (
      <div className="ci-card">
        <h2>Company Intelligence</h2>
        <p className="ci-card__empty">
          Nothing about the company itself was explicitly present in this job description.
        </p>
      </div>
    )
  }

  return (
    <div className="ci-card">
      <h2>Company Intelligence</h2>
      <p className="ci-card__lead">Extracted only from what's literally in this job description — nothing inferred.</p>

      {company.industry && (
        <div className="ci-card__row">
          <h4>Industry</h4>
          <p>{company.industry}</p>
        </div>
      )}
      {company.products_mentioned?.length > 0 && (
        <div className="ci-card__row">
          <h4>Products mentioned</h4>
          <div className="ci-card__tags">
            {company.products_mentioned.map((p) => <span key={p} className="ci-card__tag">{p}</span>)}
          </div>
        </div>
      )}
      {company.technologies_mentioned?.length > 0 && (
        <div className="ci-card__row">
          <h4>Company tech stack signal</h4>
          <div className="ci-card__tags">
            {company.technologies_mentioned.map((t) => <span key={t} className="ci-card__tag">{t}</span>)}
          </div>
        </div>
      )}
      {company.engineering_hints?.length > 0 && (
        <div className="ci-card__row">
          <h4>How this team operates</h4>
          <ul className="ci-card__list">
            {company.engineering_hints.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        </div>
      )}

      {hasSignalCategories && (
        <div className="ci-card__signals">
          {Object.entries(SIGNAL_LABELS).map(([key, label]) => {
            const items = signals[key]
            if (!items || items.length === 0) return null
            return (
              <div className="ci-card__row" key={key}>
                <h4>{label}</h4>
                <ul className="ci-card__list">
                  {items.map((h, i) => <li key={i}>{h}</li>)}
                </ul>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default CompanyIntelligenceCard