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
  const careerWorthy = active.filter((r) => r.tier === 'flagship' || r.tier === 'career')
  const onResume = careerWorthy.filter((r) => isCovered(r.name, resumeProjectNames))
  
  const missingCareerWorthy = careerWorthy.filter((r) => !isCovered(r.name, resumeProjectNames))
  const firstMissing = missingCareerWorthy[0]
  const missingLink = firstMissing ? `/resume?highlight=${encodeURIComponent(firstMissing.name)}` : '/resume'

  return (
    <section className="gh-resume-coverage">
      <h2>GitHub → Resume</h2>
      {loading ? (
        <p className="gh-resume-coverage__hint">Checking your resume…</p>
      ) : (
        <>
          <div className="gh-funnel">
            <div className="gh-funnel__step">
              <strong>{active.length}</strong>
              <span>Repositories</span>
            </div>
            <div className="gh-funnel__arrow">↓</div>
            <div className="gh-funnel__step">
              <strong>{careerWorthy.length}</strong>
              <span>Career-worthy</span>
            </div>
            <div className="gh-funnel__arrow">↓</div>
            <div className="gh-funnel__step gh-funnel__step--good">
              <strong>{onResume.length}</strong>
              <span>On resume</span>
            </div>
            <div className="gh-funnel__arrow">↓</div>
            <Link to={missingLink} className="gh-funnel__step gh-funnel__step--warn" style={{ textDecoration: 'none', cursor: 'pointer' }}>
              <strong>{careerWorthy.length - onResume.length}</strong>
              <span>Missing ⓘ</span>
            </Link>
          </div>
          <p className="gh-resume-coverage__hint" style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-soft)', display: 'block' }}>
            ⓘ On-resume status is inferred via a best-effort name-matching heuristic.
          </p>
        </>
      )}
    </section>
  )
}

export default GitHubResumeCoverage