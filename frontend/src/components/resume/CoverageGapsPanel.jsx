import CollapsibleSection from '../common/CollapsibleSection'
import './CoverageGapsPanel.css'

export default function CoverageGapsPanel({ coverage }) {
  const githubGaps = coverage?.github_not_on_resume || []
  const leetcodeGaps = coverage?.leetcode_not_on_resume || []
  const certGaps = coverage?.certificates_not_on_resume || []
  
  const totalGaps = githubGaps.length + leetcodeGaps.length + certGaps.length

  if (totalGaps === 0) {
    return (
      <CollapsibleSection title="Coverage gaps" subtitle="Evidenced elsewhere, missing from your resume" defaultOpen={false} className="cgap">
        <div className="cgap__empty">
          No coverage gaps! Your resume covers all skills evidenced in GitHub, LeetCode, and Certificates.
        </div>
      </CollapsibleSection>
    )
  }

  function handleAddClick(skill, source) {
    alert(`Add "${skill}" to your resume to close the coverage gap! Resume text editor coming soon.`);
  }

  return (
    <CollapsibleSection
      title="Coverage gaps"
      subtitle="Evidenced elsewhere, missing from your resume"
      defaultOpen={true}
      badge={<span className="cgap__badge">{totalGaps}</span>}
      className="cgap"
    >
      <div className="cgap__list">
        {githubGaps.map(skill => (
          <div className="cgap__row" key={skill}>
            <span className="cgap__skill">{skill.replace(/_/g, ' ')}</span>
            <span className="cgap__source">from GitHub</span>
            <button className="cgap__cta" onClick={() => handleAddClick(skill, 'GitHub')}>+ Add to Resume</button>
          </div>
        ))}
        {leetcodeGaps.map(skill => (
          <div className="cgap__row" key={skill}>
            <span className="cgap__skill">{skill.replace(/_/g, ' ')}</span>
            <span className="cgap__source">from LeetCode</span>
            <button className="cgap__cta" onClick={() => handleAddClick(skill, 'LeetCode')}>+ Add to Resume</button>
          </div>
        ))}
        {certGaps.map(skill => (
          <div className="cgap__row" key={skill}>
            <span className="cgap__skill">{skill.replace(/_/g, ' ')}</span>
            <span className="cgap__source">from Certificates</span>
            <button className="cgap__cta" onClick={() => handleAddClick(skill, 'Certificates')}>+ Add to Resume</button>
          </div>
        ))}
      </div>
    </CollapsibleSection>
  )
}
