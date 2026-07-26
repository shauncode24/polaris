import { useBackendStatus } from '../../hooks/useBackendStatus'
import './Footer.css'

const STATUS_LABEL = {
  checking: 'Checking backend…',
  online: 'Backend connected',
  offline: 'Backend offline',
}

// The first three items are the product's static positioning copy
// (unchanged from the design). The last one is a *real* signal, wired
// to GET /health on the FastAPI backend via useBackendStatus.
function Footer() {
  const status = useBackendStatus()

  return (
    <footer className="footer">
      <div className="container footer__inner">
        <span>Single User Mode</span>
        <span className="footer__dot" aria-hidden="true">•</span>
        <span>Powered by Local LLMs</span>
        <span className="footer__dot" aria-hidden="true">•</span>
        <span>No authentication yet</span>
        <span className="footer__dot" aria-hidden="true">•</span>
        <span className={`footer__status footer__status--${status}`}>
          <span className="footer__status-dot" />
          {STATUS_LABEL[status]}
        </span>
      </div>
    </footer>
  )
}

export default Footer
