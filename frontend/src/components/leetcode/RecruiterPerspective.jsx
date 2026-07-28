import './RecruiterPerspective.css'

function buildParagraph({ totalSolved, topicMastery, blindSpots, consistency }) {
  const strong = (topicMastery || [])
    .filter((t) => t.mastery === 'Consistent Practice' || t.mastery === 'Extensive Practice')
    .map((t) => t.topic)
  const missing = blindSpots?.missing_fundamentals || []
  const parts = []

  parts.push(
    totalSolved > 0
      ? `Across ${totalSolved} solved problems, the strongest evidence is in ${strong.length ? strong.slice(0, 3).join(', ') : 'a small, early set of topics'}.`
      : 'No LeetCode evidence has been generated yet.'
  )

  if (missing.length > 0) {
    parts.push(`Core interview topics with no solved-problem evidence yet: ${missing.slice(0, 3).join(', ')}.`)
  } else if (totalSolved > 0) {
    parts.push('Every fundamental interview topic has at least some solved-problem evidence.')
  }

  if (consistency) {
    parts.push(`Practice consistency over the last 30 days is ${consistency.toLowerCase()}.`)
  }

  if (missing.length > 0) {
    parts.push(`Closing ${missing[0]} would be the highest-leverage next step for interview readiness.`)
  }

  return parts.join(' ')
}

function RecruiterPerspective({ totalSolved, topicMastery, blindSpots, consistency }) {
  const text = buildParagraph({ totalSolved, topicMastery, blindSpots, consistency })

  return (
    <section className="lc-card recruiter-perspective">
      <h3>Recruiter perspective</h3>
      <p className="recruiter-perspective__text">{text}</p>
    </section>
  )
}

export default RecruiterPerspective