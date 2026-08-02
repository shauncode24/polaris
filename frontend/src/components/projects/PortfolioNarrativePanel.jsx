import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { getPortfolioNarrative } from '../../api/projects'
import InfoCard from '../common/InfoCard'
import { IconSparkle } from '../icons/DashboardIcons'
import './PortfolioNarrativePanel.css'

const COLLAPSE_KEY = 'projects-narrative-collapsed'

// Doc (SECTION 1): "Place Portfolio Narrative immediately below the
// header... Collapsed after first visit." The narrative itself and its
// data source are unchanged — only added a collapse toggle that persists
// via localStorage, defaulting open the very first time it's ever loaded.
function PortfolioNarrativePanel() {
  const { token } = useAuth()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(COLLAPSE_KEY) === 'true')

  async function load(regenerate = false) {
    setLoading(true)
    setError('')
    try {
      const data = await getPortfolioNarrative(token, regenerate)
      setReport(data)
    } catch (err) {
      setError(err.message || 'Could not load portfolio narrative.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem(COLLAPSE_KEY, String(next))
      return next
    })
  }

  const showToggle = report && !loading && report.eligible !== false

  return (
    <InfoCard
      icon={IconSparkle}
      iconTone="accent"
      title="Portfolio Health"
      action={
        showToggle ? (
          <button type="button" className="pnp__toggle" onClick={toggleCollapsed}>
            {collapsed ? 'Expand' : 'Collapse'}
          </button>
        ) : null
      }
    >
      {loading && <p className="pnp__loading">Reading your verified portfolio…</p>}
      {error && <p className="pnp__error">{error}</p>}
      {report && !loading && (
        report.eligible === false ? (
          <p className="pnp__ineligible">{report.narrative}</p>
        ) : collapsed ? (
          <p className="pnp__narrative pnp__narrative--collapsed">{report.narrative}</p>
        ) : (
          <div className="pnp__body">
            <p className="pnp__narrative">{report.narrative}</p>
            <div className="pnp__row"><span>Testing</span><p>{report.testing_pattern}</p></div>
            <div className="pnp__row"><span>Collaboration</span><p>{report.collaboration_pattern}</p></div>
            <div className="pnp__row"><span>Specialization</span><p>{report.specialization}</p></div>
            <div className="pnp__row pnp__row--weakness"><span>Biggest weakness</span><p>{report.biggest_weakness}</p></div>
            {report.analysis_degraded && (
              <div className="pnp__degraded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Narrative analysis degraded — showing deterministic fallback.
              </div>
            )}
            <div className="pnp__footer">
              <button type="button" className="pnp__regenerate" onClick={() => load(true)}>Regenerate</button>
              {report.generated_at && (
                <span className="pnp__generated-at">Generated {new Date(report.generated_at).toLocaleDateString()}</span>
              )}
            </div>
          </div>
        )
      )}
    </InfoCard>
  )
}

export default PortfolioNarrativePanel