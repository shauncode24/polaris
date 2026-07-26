import './Button.css'

// as="a" + href renders an anchor styled as a button; the default
// renders a real <button>. Keeps one component for every CTA on the page.
function Button({
  as: Component = 'button',
  variant = 'primary',
  size = 'md',
  icon,
  className = '',
  children,
  ...rest
}) {
  const classes = ['btn', `btn--${variant}`, `btn--${size}`, className].filter(Boolean).join(' ')

  return (
    <Component className={classes} {...rest}>
      <span>{children}</span>
      {icon}
    </Component>
  )
}

export default Button
