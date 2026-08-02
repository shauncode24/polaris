import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { getGoalAwareRanking } from '../../api/projects'
import InfoCard from '../common/InfoCard'
import { IconTarget } from '../icons/Icons'
import './GoalAwareRankingPanel.css'

function GoalAwareRankingPanel() {
  const { token } = useAuth()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      try {
        const result = await getGoalAwareRanking(token)
        setData(result)
      } catch (err) {
        setError(err.message || 'Could not load ranking.')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [token])

  return (
    <InfoCard icon={IconTarget} iconTone="accent" title="Which project should lead?">
      {loading && <p className="garp__loading">Ranking your portfolio…</p>}
      {error && <p className="garp__error">{error}</p>}
      {data && !loading && (
        data.ranked.length === 0 ? (
          <p className="garp__empty">Add projects to see a goal-aware ranking.</p>
        ) : (
          <div className="garp__body">
            {data.recommendation && <p className="garp__recommendation">{data.recommendation}</p>}
            <ol className="garp__list">
              {data.ranked.slice(0, 5).map((item, i) => (
                <li key={item.project_id} className={i === 0 ? 'garp__item garp__item--lead' : 'garp__item'}>
                  <div className="garp__item-top">
                    <span className="garp__item-name">{item.project_name}</span>
                    <span className="garp__item-score">{item.score.toFixed(2)}</span>
                  </div>
                  {item.reasons && item.reasons.length > 0 && (
                    <ul className="garp__item-reasons">
                      {item.reasons.map((reason, idx) => (
                        <li key={idx} className="garp__item-reason">{reason}</li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ol>
          </div>
        )
      )}
    </InfoCard>
  )
}

export default GoalAwareRankingPanel