import './EmptyState.css'

function EmptyState({ message, ctaLabel, onCta, ctaHref }) {
  return (
    <div className="empty-state">
      <p className="empty-state__message">{message}</p>
      {ctaLabel && (
        onCta ? (
          <button type="button" className="empty-state__cta" onClick={onCta}>
            {ctaLabel} →
          </button>
        ) : (
          <a className="empty-state__cta" href={ctaHref}>{ctaLabel} →</a>
        )
      )}
    </div>
  )
}

export default EmptyState