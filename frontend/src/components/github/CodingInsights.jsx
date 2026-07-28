import './CodingInsights.css'

function buildTags(insights) {
  const practices = insights?.engineering_practices || {}
  const doc = practices.documentation?.score ?? 0
  const testing = practices.testing?.score ?? 0
  const ci = practices.devops?.ci ?? 0
  const docker = practices.devops?.docker ?? 0
  const stale = practices.maintenance?.stale_projects ?? 0
  const active = practices.maintenance?.active_projects ?? 0

  const strengths = []
  const needsImprovement = []

  if (doc >= 60) strengths.push('Documentation')
  else needsImprovement.push('Documentation')

  if (testing >= 50) strengths.push('Testing')
  else needsImprovement.push('Testing')

  if (ci > 0) strengths.push('CI/CD')
  else needsImprovement.push('CI/CD')

  if (docker > 0) strengths.push('Docker')
  if (active >= stale) strengths.push('Active maintenance')
  else needsImprovement.push('Stale repositories')

  return { strengths: [...new Set(strengths)], needsImprovement: [...new Set(needsImprovement)] }
}

function CodingInsights({ insights }) {
  const { strengths, needsImprovement } = buildTags(insights)

  return (
    <section className="gh-coding">
      <h2>Coding insights</h2>

      <div className="gh-coding__group">
        <span className="gh-coding__label gh-coding__label--strength">Strengths</span>
        <div className="gh-coding__tags">
          {strengths.length > 0 ? (
            strengths.map((t) => (
              <span key={t} className="gh-coding__tag gh-coding__tag--strength">{t}</span>
            ))
          ) : (
            <span className="gh-coding__empty">Not enough evidence yet.</span>
          )}
        </div>
      </div>

      <div className="gh-coding__group">
        <span className="gh-coding__label gh-coding__label--gap">Needs improvement</span>
        <div className="gh-coding__tags">
          {needsImprovement.length > 0 ? (
            needsImprovement.map((t) => (
              <span key={t} className="gh-coding__tag gh-coding__tag--gap">{t}</span>
            ))
          ) : (
            <span className="gh-coding__empty">No major gaps detected.</span>
          )}
        </div>
      </div>
    </section>
  )
}

export default CodingInsights