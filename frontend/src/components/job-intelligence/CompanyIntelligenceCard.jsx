// frontend/src/components/job-intelligence/CompanyIntelligenceCard.jsx
import { useState } from 'react'
import './CompanyIntelligenceCard.css'

function RecognitionList({ items }) {
  const [expanded, setExpanded] = useState(false)
  if (!items || items.length === 0) return null
  const visible = expanded ? items : items.slice(0, 2)
  const remaining = items.length - visible.length

  return (
    <ul className="ci-card__list">
      {visible.map((h, i) => <li key={i}>{h}</li>)}
      {remaining > 0 && (
        <li>
          <button type="button" className="ci-card__more-btn" onClick={() => setExpanded(true)}>
            +{remaining} more
          </button>
        </li>
      )}
    </ul>
  )
}

function CompanyIntelligenceCard({ company }) {
  const signals = company?.company_signals || {}
  const hasSignalCategories = Object.values(signals).some((arr) => arr?.length > 0)
  const hasSignal =
    company &&
    (company.industry ||
      company.domain?.length ||
      company.products_mentioned?.length ||
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
      {company.domain?.length > 0 && (
        <div className="ci-card__row">
          <h4>Business domains</h4>
          <div className="ci-card__tags">
            {company.domain.map((d) => <span key={d} className="ci-card__tag">{d}</span>)}
          </div>
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

      {(company.engineering_hints?.length > 0 || signals.culture?.length > 0) && (
        <div className="ci-card__row">
          <h4>How they operate</h4>
          <ul className="ci-card__list">
            {(company.engineering_hints || []).map((h, i) => <li key={`eh-${i}`}>{h}</li>)}
            {(signals.culture || []).map((h, i) => <li key={`c-${i}`}>{h}</li>)}
          </ul>
        </div>
      )}

      {signals.values?.length > 0 && (
        <div className="ci-card__row">
          <h4>Values</h4>
          <div className="ci-card__tags">
            {signals.values.map((v, i) => <span key={i} className="ci-card__tag">{v}</span>)}
          </div>
        </div>
      )}

      {signals.work_environment?.length > 0 && (
        <div className="ci-card__row">
          <h4>Work environment</h4>
          <div className="ci-card__tags">
            {signals.work_environment.map((v, i) => <span key={i} className="ci-card__tag">{v}</span>)}
          </div>
        </div>
      )}

      {(signals.learning_development?.length > 0 || signals.diversity_inclusion?.length > 0 || signals.recognition?.length > 0) && (
        <div className="ci-card__people-culture">
          <h4>People & culture</h4>
          <div className="ci-card__people-grid">
            {signals.learning_development?.length > 0 && (
              <div>
                <h5>Learning & development</h5>
                <ul className="ci-card__list">
                  {signals.learning_development.map((h, i) => <li key={i}>{h}</li>)}
                </ul>
              </div>
            )}
            {signals.diversity_inclusion?.length > 0 && (
              <div>
                <h5>Diversity & inclusion</h5>
                <ul className="ci-card__list">
                  {signals.diversity_inclusion.map((h, i) => <li key={i}>{h}</li>)}
                </ul>
              </div>
            )}
            {signals.recognition?.length > 0 && (
              <div>
                <h5>Recognition</h5>
                <RecognitionList items={signals.recognition} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default CompanyIntelligenceCard