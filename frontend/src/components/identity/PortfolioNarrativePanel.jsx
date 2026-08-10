// frontend/src/components/identity/PortfolioNarrativePanel.jsx
// Surfaces the portfolio_narrative field now present on IdentityFacts — the
// Projects module's portfolio-wide analysis (testing pattern, collaboration
// pattern, specialization, biggest weakness) that was computed but never
// displayed on the Identity page before.
import CollapsibleSection from '../common/CollapsibleSection'
import './PortfolioNarrativePanel.css'

const DIMENSION_META = {
  testing_pattern: {
    label: 'Testing Pattern',
    icon: '✓',
    tone: 'neutral',
    description: 'How consistently you write tests across your projects.',
  },
  collaboration_pattern: {
    label: 'Collaboration',
    icon: '⇆',
    tone: 'neutral',
    description: 'Solo vs. collaborative work visible across your portfolio.',
  },
  specialization: {
    label: 'Specialisation',
    icon: '◈',
    tone: 'strong',
    description: 'The emerging technical identity your projects point toward.',
  },
  biggest_weakness: {
    label: 'Biggest Weakness',
    icon: '▽',
    tone: 'warn',
    description: 'The most consistent gap the portfolio reveals.',
  },
}

function DimensionCard({ dimensionKey, value }) {
  const meta = DIMENSION_META[dimensionKey]
  if (!meta || !value?.trim()) return null

  return (
    <div className={`pnp__card pnp__card--${meta.tone}`}>
      <div className="pnp__card-header">
        <span className="pnp__card-icon" aria-hidden="true">{meta.icon}</span>
        <span className="pnp__card-label">{meta.label}</span>
      </div>
      <p className="pnp__card-value">{value}</p>
    </div>
  )
}

function PortfolioNarrativePanel({ portfolioNarrative }) {
  if (!portfolioNarrative) return null

  const { narrative, testing_pattern, collaboration_pattern, specialization, biggest_weakness, analysis_degraded } =
    portfolioNarrative

  const hasDimensions =
    testing_pattern || collaboration_pattern || specialization || biggest_weakness

  if (!narrative && !hasDimensions) return null

  return (
    <CollapsibleSection
      title="Portfolio Pattern"
      subtitle="Cross-project analysis · Testing · Collaboration · Specialisation"
      defaultOpen={true}
    >
      <div className="pnp">
        {analysis_degraded && (
          <p className="pnp__degraded-note">
            ⚠ This analysis used a fallback due to a temporary LLM issue — details may be approximate.
          </p>
        )}

        {narrative && (
          <p className="pnp__narrative">{narrative}</p>
        )}

        {hasDimensions && (
          <div className="pnp__grid">
            <DimensionCard dimensionKey="testing_pattern"       value={testing_pattern} />
            <DimensionCard dimensionKey="collaboration_pattern" value={collaboration_pattern} />
            <DimensionCard dimensionKey="specialization"        value={specialization} />
            <DimensionCard dimensionKey="biggest_weakness"      value={biggest_weakness} />
          </div>
        )}
      </div>
    </CollapsibleSection>
  )
}

export default PortfolioNarrativePanel
