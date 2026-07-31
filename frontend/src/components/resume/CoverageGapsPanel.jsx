import CollapsibleSection from '../common/CollapsibleSection'
import './CoverageGapsPanel.css'

export default function CoverageGapsPanel({ coverage }) {
  const githubGaps = coverage?.github_gaps || []
  const leetcodeGaps = coverage?.leetcode_gaps || []
  const certGaps = coverage?.certificate_gaps || []
  const projectSuggestions = coverage?.project_suggestions || []
  const timelineNotes = coverage?.timeline_plausibility_notes || []
  
  const totalGaps = githubGaps.length + leetcodeGaps.length + certGaps.length + projectSuggestions.length + timelineNotes.length

  if (totalGaps === 0) {
    return (
      <CollapsibleSection title="Coverage gaps & timeline" subtitle="Evidenced elsewhere, missing from your resume" defaultOpen={false} className="cgap">
        <div className="cgap__empty">
          No coverage gaps or timeline advisories detected!
        </div>
      </CollapsibleSection>
    )
  }

  function handleAddClick(skill) {
    alert(`Add "${skill}" to your resume to close the coverage gap! Resume text editor coming soon.`);
  }

  function handleAddProjectClick(repoName) {
    alert(`Showcase project "${repoName}" on your resume! Resume text editor coming soon.`);
  }

  return (
    <CollapsibleSection
      title="Coverage gaps & timeline"
      subtitle="Evidenced elsewhere, missing from your resume or conflicting with claims"
      defaultOpen={true}
      badge={<span className="cgap__badge">{totalGaps}</span>}
      className="cgap"
    >
      <div className="cgap__list">
        {timelineNotes.map((note, idx) => (
          <div className="cgap__row cgap__row--advisory" key={`timeline-${idx}-${note.skill}`}>
            <div className="cgap__text-col">
              <span className="cgap__skill">{note.skill.replace(/_/g, ' ')}</span>
              <p className="cgap__reason">{note.detail}</p>
            </div>
            <span className="cgap__source cgap__source--advisory">Timeline Advisory</span>
          </div>
        ))}
        {githubGaps.map(gap => (
          <div className="cgap__row" key={gap.skill}>
            <div className="cgap__text-col">
              <span className="cgap__skill">{gap.skill.replace(/_/g, ' ')}</span>
              <p className="cgap__reason">{gap.reason}</p>
            </div>
            <span className="cgap__source cgap__source--github">GitHub</span>
            <button className="cgap__cta" onClick={() => handleAddClick(gap.skill)}>+ Add</button>
          </div>
        ))}
        {projectSuggestions.map(proj => (
          <div className="cgap__row cgap__row--project" key={proj.repo_name}>
            <div className="cgap__text-col">
              <span className="cgap__skill">{proj.repo_name}</span>
              <p className="cgap__reason">{proj.reason}</p>
            </div>
            <span className="cgap__source cgap__source--suggest">Suggestion</span>
            <button className="cgap__cta cgap__cta--showcase" onClick={() => handleAddProjectClick(proj.repo_name)}>+ Showcase</button>
          </div>
        ))}
        {leetcodeGaps.map(gap => (
          <div className="cgap__row" key={gap.skill}>
            <div className="cgap__text-col">
              <span className="cgap__skill">{gap.skill.replace(/_/g, ' ')}</span>
              <p className="cgap__reason">{gap.reason}</p>
            </div>
            <span className="cgap__source cgap__source--leetcode">LeetCode</span>
            <button className="cgap__cta" onClick={() => handleAddClick(gap.skill)}>+ Add</button>
          </div>
        ))}
        {certGaps.map(gap => (
          <div className="cgap__row" key={gap.skill}>
            <div className="cgap__text-col">
              <span className="cgap__skill">{gap.skill.replace(/_/g, ' ')}</span>
              <p className="cgap__reason">{gap.reason}</p>
            </div>
            <span className="cgap__source cgap__source--cert">Certificate</span>
            <button className="cgap__cta" onClick={() => handleAddClick(gap.skill)}>+ Add</button>
          </div>
        ))}
      </div>
    </CollapsibleSection>
  )
}
