import Card from './Card'
import './InfoCard.css'

function InfoCard({ icon: Icon, iconTone = 'default', title, badge, action, children, className = '' }) {
  return (
    <Card className={`info-card ${className}`}>
      <div className="info-card__header">
        <div className="info-card__title-group">
          {Icon && <span className={`info-card__icon info-card__icon--${iconTone}`}><Icon size={16} /></span>}
          <h3 className="info-card__title">{title}</h3>
        </div>
        {badge}
        {action}
      </div>
      <div className="info-card__body">{children}</div>
    </Card>
  )
}

export default InfoCard