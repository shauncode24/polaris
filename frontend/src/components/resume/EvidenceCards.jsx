import './EvidenceCards.css'

const MAX_SOURCES = 5 // experience, project, github, leetcode, certificate

const LEVEL_LABEL = { high: 'Strong', medium: 'Medium', low: 'Weak' }

function Stars({ count }) {
  return (
    <span className="evcard__stars" aria-label={`${count} of ${MAX_SOURCES}`}>
      {Array.from({ length: MAX_SOURCES }).map((_, i) => (
        <span key={i} className={i < count ? 'evcard__star evcard__star--on' : 'evcard__star'}>★</span>
      ))}
    </span>
  )
}

export default function EvidenceCards({ skills = [] }) {
  if (skills.length === 0) {
    return <div className="evcard__empty">No skill evidence collected yet.</div>
  }

  return (
    <div className="evcard__grid">
      {skills.map((skill) => {
        const level = skill.corroboration_level || 'low'
        const sources = [
          skill.in_experience && 'Experience',
          skill.in_project && 'Projects',
          skill.in_github && 'GitHub',
          skill.in_leetcode && 'LeetCode',
          skill.in_certificate && 'Certificates',
        ].filter(Boolean)

        return (
          <div className="evcard" key={skill.canonical}>
            <div className="evcard__head">
              <span className="evcard__name">{skill.name}</span>
              <span className={`evcard__level evcard__level--${level}`}>{LEVEL_LABEL[level]}</span>
            </div>
            <Stars count={skill.corroboration_count || 0} />
            <div className="evcard__sources">
              {sources.length > 0 ? (
                sources.map((s) => <span className="evcard__source" key={s}>✓ {s}</span>)
              ) : (
                <span className="evcard__source evcard__source--none">No corroborating source</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}