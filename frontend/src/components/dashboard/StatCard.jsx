import Card from '../common/Card'
import './StatCard.css'

function StatCard({ icon: Icon, label, value, subLabel }) {
  return (
    <Card className="stat-card">
      <div className="stat-card__top">
        <span className="stat-card__label">{label}</span>
        {Icon && <Icon size={16} className="stat-card__icon" />}
      </div>
      <span className="stat-card__value">{value}</span>
      {subLabel && <span className="stat-card__sub">{subLabel}</span>}
    </Card>
  )
}

export default StatCard