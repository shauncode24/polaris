// The headings of a good answer, with the user's own words under the ones their
// record speaks to.
export default function AnswerOutline({ outline }) {
  const { story, sections, other_facts: otherFacts, warnings } = outline
  return (
    <div className="ik-outline">
      {warnings.map((warning) => <p key={warning} className="ik-warning">{warning}</p>)}

      {story && (
        <div className="ik-outline__story">
          <strong>{story.title}</strong>
          {story.period && <span className="ik-hint">{story.period}</span>}
          {story.url && <a href={story.url} target="_blank" rel="noopener noreferrer">Open on GitHub</a>}
          {story.technologies.length > 0 && <span className="ik-hint">{story.technologies.join(', ')}</span>}
        </div>
      )}

      <dl>
        {sections.map((section) => (
          <div key={section.heading}>
            <dt>{section.heading}</dt>
            <dd className="ik-hint">{section.prompt}</dd>
            {section.facts.map((fact) => <dd key={fact.text} className="ik-fact">{fact.text}</dd>)}
          </div>
        ))}
      </dl>

      {otherFacts.length > 0 && (
        <div>
          <p className="ik-label">Also from this work</p>
          <ul className="ik-list">
            {otherFacts.map((fact) => <li key={fact.bullet ?? fact.text}>{fact.text}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
