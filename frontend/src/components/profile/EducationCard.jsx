import Card from '../common/Card'
import './ProfileSectionCard.css'

function EducationCard({ results, loading }) {
  const education = results?.resume?.education || []

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 10l10-6 10 6-10 6z" />
              <path d="M6 12v6c0 1 2 3 6 3s6-2 6-3v-6" />
            </svg>
          </span>
          <h3 className="psc__title">Education</h3>
          {education.length > 0 && (
            <span className="psc__count">{education.length}</span>
          )}
        </div>
        <button type="button" className="psc__add-btn">
          <span>+</span> Add education manually
        </button>
      </div>

      {loading ? (
        <div className="psc__empty">
          <span className="psc__empty-text">Loading…</span>
        </div>
      ) : education.length === 0 ? (
        <div className="psc__empty">
          <span className="psc__empty-text">No education records found — upload a resume to extract them.</span>
        </div>
      ) : (
        education.map((edu, i) => (
          <div key={edu.id || i} className="psc__item">
            <div className="psc__item-header">
              <div>
                <div className="psc__item-title">{edu.institution || edu.school || 'Institution'}</div>
                <div className="psc__item-sub">
                  {edu.degree || edu.field_of_study || 'Degree'}
                  {edu.graduation_year && <><br />{edu.graduation_year}</>}
                </div>
              </div>
              <div className="psc__item-actions">
                <button type="button" className="psc__item-action-btn">Edit</button>
                <button type="button" className="psc__item-action-btn psc__item-action-btn--danger" aria-label="Delete education">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 7h16" /><path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                    <path d="M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        ))
      )}
    </Card>
  )
}

export default EducationCard
