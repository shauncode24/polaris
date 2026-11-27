// frontend/src/components/job-intelligence/JobComparison.jsx
import './JobComparison.css'

const STATUS_LABELS = { have: 'You have it', partial: 'Partly', missing: 'Gap' }
const BAND_LABELS = { required: 'Required', implicit: 'Implied', nice_to_have: 'Nice to have' }

function skillName(skill) {
  return skill.replace(/_/g, ' ')
}

function JobComparison({ data }) {
  const { jobs, skills } = data

  return (
    <div className="job-compare">
      <div className="job-compare__cards">
        {jobs.map((job) => (
          <article key={job.id} className="job-compare__card">
            {job.is_primary && <span className="job-compare__primary">★ Primary target</span>}
            <h3>{job.role || 'Untitled role'}</h3>
            <p>{job.company || '—'}</p>
            {job.overall_match ? (
              <>
                <strong>{Math.round(job.overall_match.percentage)}%</strong>
                <p>
                  {job.overall_match.label} · required {job.overall_match.required_matched} · nice to have{' '}
                  {job.overall_match.nice_to_have_matched}
                </p>
              </>
            ) : (
              <p>No skills were extracted from this posting.</p>
            )}
          </article>
        ))}
      </div>

      {skills.length > 0 && (
        <div className="job-compare__table-wrap">
          <table className="job-compare__table">
            <thead>
              <tr>
                <th scope="col">Skill</th>
                <th scope="col">You</th>
                {jobs.map((job) => (
                  <th key={job.id} scope="col">
                    {job.role || 'Untitled role'}
                    {job.company && <span>{job.company}</span>}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {skills.map((row) => (
                <tr key={row.skill}>
                  <th scope="row">{skillName(row.skill)}</th>
                  <td>
                    <span className={`job-compare__status job-compare__status--${row.status}`}>
                      {STATUS_LABELS[row.status]}
                    </span>
                  </td>
                  {jobs.map((job) => {
                    const band = row.bands[job.id]
                    return (
                      <td key={job.id} className={band ? `job-compare__band--${band}` : 'job-compare__none'}>
                        {band ? BAND_LABELS[band] : '—'}
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default JobComparison
