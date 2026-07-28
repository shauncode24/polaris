import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeVersions.css'

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function ResumeVersions({ versions = [] }) {
  return (
    <CollapsibleSection title="Version History" defaultOpen={false} className="rver">
      <div className="rver__body">
        {versions.length === 0 ? (
          <div style={{ padding: '16px 18px', fontSize: 13, color: 'var(--text-soft)' }}>
            No upload history yet.
          </div>
        ) : (
          versions.map((v) => (
            <div className="rver__item" key={v.id}>
              <div className={`rver__dot ${v.is_current ? 'rver__dot--current' : ''}`} />
              <div className="rver__info">
                <div className="rver__ver">
                  {v.version}
                  {v.is_current && <span className="rver__current-badge">Current</span>}
                </div>
                <div className="rver__filename">{v.filename || 'resume.pdf'}</div>
              </div>
              <div className="rver__date">{formatDate(v.created_at)}</div>
            </div>
          ))
        )}
      </div>
    </CollapsibleSection>
  )
}
