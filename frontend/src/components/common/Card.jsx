import './Card.css'

function Card({ as: Component = 'div', className = '', children, ...rest }) {
  return (
    <Component className={`ui-card ${className}`} {...rest}>
      {children}
    </Component>
  )
}

export default Card