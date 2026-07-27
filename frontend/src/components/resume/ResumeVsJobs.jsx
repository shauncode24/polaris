import './ResumeVsJobs.css'

function pctClass(pct) {
  if (pct == null) return ''
  if (pct >= 70) return 'rvj__pct--high'
  if (pct >= 45) return 'rvj__pct--mid'
  return 'rvj__pct--low'
}

export default function ResumeVsJobs({ resume_vs_jobs = [] }) {
  return (
    <div className="rvj">
      <div className="rvj__header">
        <span className="rvj__title">Resume vs. Jobs</span>
      </div>
      <div className="rvj__body">
        {resume_vs_jobs.length === 0 ? (
          <div className="rvj__empty">
            Analyze a job to see how your resume stacks up.
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
    </div>
  )
}
