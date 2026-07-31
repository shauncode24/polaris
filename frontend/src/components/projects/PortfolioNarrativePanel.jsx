import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { getPortfolioNarrative } from '../../api/projects'
import InfoCard from '../common/InfoCard'
import { IconSparkle } from '../icons/DashboardIcons'
import './PortfolioNarrativePanel.css'

function PortfolioNarrativePanel() {
  const { token } = useAuth()
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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

  return (
    <InfoCard icon={IconSparkle} iconTone="accent" title="Portfolio Narrative">
      {loading && <p className="pnp__loading">Reading your verified portfolio…</p>}
      {error && <p className="pnp__error">{error}</p>}
      {report && !loading && (
        report.eligible === false ? (
          <p className="pnp__ineligible">{report.narrative}</p>
        ) : (
          <div className="pnp__body">
            <p className="pnp__narrative">{report.narrative}</p>
            <div className="pnp__row"><span>Testing</span><p>{report.testing_pattern}</p></div>
            <div className="pnp__row"><span>Collaboration</span><p>{report.collaboration_pattern}</p></div>
            <div className="pnp__row"><span>Specialization</span><p>{report.specialization}</p></div>
            <div className="pnp__row pnp__row--weakness"><span>Biggest weakness</span><p>{report.biggest_weakness}</p></div>
            <button type="button" className="pnp__regenerate" onClick={() => load(true)}>Regenerate</button>
          </div>
        )
      )}
    </InfoCard>
  )
}

export default PortfolioNarrativePanel