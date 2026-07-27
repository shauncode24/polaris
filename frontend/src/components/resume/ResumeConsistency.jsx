import './ResumeConsistency.css'

export default function ResumeConsistency({ profile_consistency }) {
  if (!profile_consistency) return null

  const { profile_skill_count, resume_skill_count, missing_from_resume } = profile_consistency
  const pct = profile_skill_count > 0
    ? Math.round((resume_skill_count / profile_skill_count) * 100)
    : 100
  const allCovered = missing_from_resume.length === 0

  return (
    <div className="rcons">
      <div className="rcons__header">
        <span className="rcons__title">Profile Consistency</span>
      </div>
      <div className="rcons__body">
        <div className="rcons__ratio-row">
          <div className="rcons__ratio-text">{pct}%</div>
          <div className="rcons__bar-wrap">
            <div className="rcons__bar-track">
              <div className="rcons__bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="rcons__bar-label">
              {resume_skill_count} of {profile_skill_count} profile skills appear in resume
            </div>
          </div>
        </div>

        {allCovered ? (
          <div className="rcons__empty">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            All profile skills are represented in your resume.
          </div>
        ) : (
          <>
            <div className="rcons__missing-title">Missing from resume</div>
            <div className="rcons__tags">
              {missing_from_resume.map((skill) => (
                <span className="rcons__tag" key={skill}>{skill}</span>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
