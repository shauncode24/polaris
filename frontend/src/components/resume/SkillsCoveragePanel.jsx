import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import EvidenceCards from './EvidenceCards'
import CoverageGapsPanel from './CoverageGapsPanel'
import './SkillsCoveragePanel.css'

export default function SkillsCoveragePanel({ profile_consistency, evidence, coverage_gaps }) {
  const [showDetail, setShowDetail] = useState(false)

  if (!profile_consistency && !evidence) return null

  const { profile_skill_count = 0, resume_skill_count = 0, missing_from_resume = [] } = profile_consistency || {}
  const pct = profile_skill_count > 0 ? Math.round((resume_skill_count / profile_skill_count) * 100) : 100

  const high = evidence?.high_corroboration ?? 0
  const medium = evidence?.medium_corroboration ?? 0
  const low = evidence?.low_corroboration ?? 0

  return (
    <CollapsibleSection title="Skills & Coverage" subtitle={`${pct}% of profile skills represented`} defaultOpen={true} className="scov">
      <div className="scov__body">
        <div className="scov__ratio-row">
          <div className="scov__ratio-text">{pct}%</div>
          <div className="scov__bar-wrap">
            <div className="scov__bar-track">
              <div className="scov__bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="scov__bar-label">
              {resume_skill_count} of {profile_skill_count} profile skills appear in your resume
            </div>
          </div>
        </div>

        {missing_from_resume.length > 0 && (
          <div>
            <div className="scov__section-label">Missing Skills</div>
            <div className="scov__chips">
              {missing_from_resume.slice(0, 10).map((skill) => (
                <span className="scov__chip" key={skill}>{skill}</span>
              ))}
            </div>
          </div>
        )}

        {evidence && (
          <div>
            <div className="scov__section-label">Evidence Strength</div>
            <div className="scov__legend">
              <span className="scov__legend-item"><span className="scov__dot scov__dot--high" />{high} Strong</span>
              <span className="scov__legend-item"><span className="scov__dot scov__dot--medium" />{medium} Medium</span>
              <span className="scov__legend-item"><span className="scov__dot scov__dot--low" />{low} Weak</span>
            </div>
          </div>
        )}

        <button type="button" className="scov__detail-toggle" onClick={() => setShowDetail(v => !v)}>
          {showDetail ? 'Hide Detailed Evidence ▲' : 'View Detailed Evidence ▼'}
        </button>

        {showDetail && (
          <div className="scov__detail">
            {evidence?.skills?.length > 0 && (
              <div>
                <div className="scov__section-label">Skill Evidence</div>
                <EvidenceCards skills={evidence.skills} />
              </div>
            )}
            {coverage_gaps && (
              <div className="scov__gaps-wrap">
                <CoverageGapsPanel coverage={coverage_gaps} />
              </div>
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}