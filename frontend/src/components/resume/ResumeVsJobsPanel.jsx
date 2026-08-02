import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeVsJobsPanel.css'

function pctClass(pct) {
  if (pct == null) return ''
  if (pct >= 70) return 'rvj__pct--high'
  if (pct >= 40) return 'rvj__pct--mid'
  return 'rvj__pct--low'
}

export default function ResumeVsJobsPanel({ resume_vs_jobs = [] }) {
  const meaningful = resume_vs_jobs.filter(j => j.match_pct != null && j.match_pct > 0)

  if (meaningful.length === 0) return null

  return (
    <CollapsibleSection title="Job Matches" defaultOpen={true} className="rvj">
      <div className="rvj__body">
        {meaningful.map((job) => (
          <div className="rvj__item" key={job.id}>
            <div className="rvj__info">
              <div className="rvj__role">{job.role}</div>
              <div className="rvj__company">{job.company}</div>
            </div>
            <div className={`rvj__pct ${pctClass(job.match_pct)}`}>{job.match_pct}%</div>
          </div>
        ))}
      </div>
    </CollapsibleSection>
  )
}