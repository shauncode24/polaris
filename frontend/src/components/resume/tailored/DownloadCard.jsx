import { useState } from 'react'

const FORMATS = [
  { key: 'pdf', label: 'Download PDF' },
  { key: 'docx', label: 'Download Word' },
]

// The two downloads, with what to know before sending the file. `onDownload`
// saves the chosen format and throws with a message if it can't.
export default function DownloadCard({ waiting, evidence, busy, onDownload }) {
  const [downloading, setDownloading] = useState(null)
  const [error, setError] = useState('')
  const removed = Object.values(evidence).some((item) => !item.available)

  async function download(format) {
    setDownloading(format)
    setError('')
    try {
      await onDownload(format)
    } catch (err) {
      setError(err.message || 'Could not download the file.')
    } finally {
      setDownloading(null)
    }
  }

  return (
    <section className="tr-card tr-download" aria-label="Download">
      <div className="tr-actions">
        {FORMATS.map(({ key, label }) => (
          <button
            type="button"
            key={key}
            className="tr-btn tr-btn--primary"
            disabled={busy || downloading !== null}
            onClick={() => download(key)}
          >
            {downloading === key ? 'Preparing…' : label}
          </button>
        ))}
      </div>
      <p className="tr-hint">
        The file holds the resume as saved and shown below.
        {waiting > 0 && ` ${waiting === 1 ? 'The suggestion' : `The ${waiting} suggestions`} still waiting for your decision ${waiting === 1 ? 'is' : 'are'} not included.`}
      </p>
      {removed && (
        <p className="tr-banner">
          Parts of this resume rest on items you have since removed or hidden. Check them, or generate a new
          version, before sending it.
        </p>
      )}
      {error && <p className="tr-line__error" role="alert">{error}</p>}
    </section>
  )
}
