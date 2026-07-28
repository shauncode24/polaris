import { confidenceTier, confidenceLabel } from '../../utils/leetcodeMastery'
import { supportsFor } from '../../utils/topicSupports'
import './EvidenceGenerated.css'

function EvidenceGenerated({ topicMastery }) {
  const practiced = (topicMastery || [])
    .filter((t) => t.problems > 0)
    .sort((a, b) => b.problems - a.problems)
    .slice(0, 4)

  function handleAddToResume(topic) {
    alert(`Add "${topic}" evidence to your resume! Resume text editor coming soon.`)
  }

  return (
    <section className="lc-card">
      <div className="lc-evidence__header">
        <div>
          <h2>Evidence generated</h2>
          <p className="lc-card__lead">LeetCode becomes verifiable skill evidence, not just a scorecard.</p>
        </div>
        <span className="lc-evidence__pill">Feeds your profile</span>
      </div>

      {practiced.length === 0 ? (
        <p className="lc-empty-text">Sync your LeetCode account to start generating evidence.</p>
      ) : (
        <div className="lc-evidence__grid">
          {practiced.map((t) => {
            const tier = confidenceTier(t.mastery)
            return (
              <div className="lc-evidence__card" key={t.topic}>
                <div className="lc-evidence__card-row">
                  <span className="lc-evidence__card-name">{t.topic}</span>
                  <span className={`lc-topic__badge lc-topic__badge--${tier}`}>{confidenceLabel(tier)} confidence</span>
                </div>
                <span className="lc-evidence__card-detail">
                  {t.problems} solved problem{t.problems === 1 ? '' : 's'} · {t.mastery}
                </span>
                <div className="lc-evidence__supports">
                  {supportsFor(t.topic).map((s) => <span key={s} className="lc-evidence__support-tag">{s}</span>)}
                </div>
                <button type="button" className="lc-evidence__add-btn" onClick={() => handleAddToResume(t.topic)}>
                  + Add to resume
                </button>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

export default EvidenceGenerated