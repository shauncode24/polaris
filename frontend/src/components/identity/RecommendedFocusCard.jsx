import Card from '../common/Card'
import './RecommendedFocusCard.css'

function RecommendedFocusCard({ text }) {
  if (!text) return null
  return (
    <Card className="focus-card">
      <span className="focus-card__eyebrow">Recommended Focus</span>
      <p className="focus-card__text">{text}</p>
    </Card>
  )
}

export default RecommendedFocusCard