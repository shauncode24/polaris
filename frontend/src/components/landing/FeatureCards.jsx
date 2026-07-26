import { IconDocument, IconTarget, IconChat } from '../icons/Icons'
import './FeatureCards.css'

const FEATURES = [
  {
    icon: IconDocument,
    title: 'Resume Intelligence',
    description: 'Extract skills, projects and experiences from your resume.',
  },
  {
    icon: IconTarget,
    title: 'Career Intelligence',
    description: 'Match yourself against real job descriptions and identify skill gaps.',
  },
  {
    icon: IconChat,
    title: 'Interview Intelligence',
    description: 'Practice behavioral interviews using your real experiences.',
  },
]

function FeatureCards() {
  return (
    <section className="features">
      <div className="container features__grid">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <article className="feature-card" key={title}>
            <span className="feature-card__icon">
              <Icon size={20} />
            </span>
            <h3 className="feature-card__title">{title}</h3>
            <p className="feature-card__desc">{description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export default FeatureCards
