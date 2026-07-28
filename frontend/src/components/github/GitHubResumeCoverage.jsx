import { Link } from 'react-router-dom'
import './GitHubResumeCoverage.css'

function isCovered(repoName, resumeProjectNames) {
  const lower = repoName.toLowerCase()
  return resumeProjectNames.some((name) => {
    const n = name.toLowerCase()
    return n.includes(lower) || lower.includes(n)
  })
}

function GitHubResumeCoverage({ repositories, resumeProjectNames, loading }) {
  const active = repositories.filter((r) => !r.archived)
  const missing = active.filter((r) => !isCovered(r.name, resumeProjectNames))

  return (
    <section className="gh-resume-coverage">
      <h2>GitHub → Resume</h2>
      {loading ? (
        <p className="gh-resume-coverage__hint">Checking your resume…</p>
      ) : (
        <>
          <p className="gh-resume-coverage__hint">
            {active.length} repositor{active.length === 1 ? 'y' : 'ies'}, but only{' '}
            {active.length - missing.length} appear as resume projects.
          </p>
          {missing.length > 0 && (
            <div className="gh-resume-coverage__chips">
              {missing.slice(0, 6).map((r) => (
                <span key={r.name} className="gh-resume-coverage__chip">{r.name}</span>
              ))}
            </div>
          )}
          <Link to="/profile" className="gh-resume-coverage__link">Review coverage →</Link>
        </>
      )}
    </section>
  )
}

export default GitHubResumeCoverage