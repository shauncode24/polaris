import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeVsJobsPanel.css'

function pctClass(pct) {
  if (pct == null) return ''
  if (pct >= 70) return 'rvj__pct--high'
  if (pct >= 40) return 'rvj__pct--mid'
  return 'rvj__pct--low'
}

export default function ResumeVsJobsPanel({ resume_vs_jobs = [] }) {
  return (
    <CollapsibleSection title="Job Matches" defaultOpen={true} className="rvj">
      <div className="rvj__body">
        {resume_vs_jobs.length === 0 ? (
          <div className="rvj__empty">
            No job matches computed. Create job analyses to see matches.
          </div>
        ) : (
          resume_vs_jobs.map((job) => (
            <div className="rvj__item" key={job.id}>
              <div className="rvj__info">
                <div className="rvj__role">{job.role}</div>
                <div className="rvj__company">{job.company}</div>
              </div>
              <div className={`rvj__pct ${pctClass(job.match_pct)}`}>
                {job.match_pct != null ? `${job.match_pct}%` : '—'}
              </div>
            </div>
          ))
        )}
      </div>
    </CollapsibleSection>
  )
}
