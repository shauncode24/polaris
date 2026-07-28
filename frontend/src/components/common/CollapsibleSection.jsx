import { useState } from 'react'
import './CollapsibleSection.css'

function CollapsibleSection({
  title,
  subtitle,
  badge,
  defaultOpen = true,
  dense = false,
  actions,
  className,
  children,
}) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div className={`csec ${dense ? 'csec--dense' : ''} ${className || ''}`}>
      <button
        type="button"
        className="csec__header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className={`csec__chevron ${open ? 'csec__chevron--open' : ''}`}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 6l6 6-6 6" />
          </svg>
        </span>
        <span className="csec__title-group">
          <span className="csec__title">{title}</span>
          {subtitle && <span className="csec__subtitle">{subtitle}</span>}
        </span>
        {badge}
      </button>
      {actions && <div className="csec__actions" onClick={(e) => e.stopPropagation()}>{actions}</div>}
      {open && <div className="csec__body">{children}</div>}
    </div>
  )
}

export default CollapsibleSection
