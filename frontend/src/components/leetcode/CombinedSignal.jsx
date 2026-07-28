import { useProfileData } from '../../contexts/ProfileDataContext'
import './CombinedSignal.css'

function CombinedSignal({ topicMastery }) {
  const { results } = useProfileData()
  const github = results.github

  const practicedTopics = (topicMastery || [])
    .filter((t) => t.problems > 0)
    .sort((a, b) => b.problems - a.problems)
    .slice(0, 4)
    .map((t) => t.topic)

  const languages = (github?.summary?.languages_detected || [])
    .slice(0, 4)
    .map((l) => l.language || l)

  if (!github && practicedTopics.length === 0) return null

  return (
    <section className="lc-card combined-signal">
      <h3>Combined signal</h3>
      <p className="lc-card__lead">What GitHub and LeetCode evidence say together — not a score, just what's actually there.</p>

      <div className="combined-signal__cols">
        <div>
          <span className="combined-signal__label">From GitHub</span>
          {languages.length > 0 ? (
            <div className="combined-signal__pills">
              {languages.map((l) => <span key={l} className="combined-signal__pill">{l}</span>)}
            </div>
          ) : <p className="combined-signal__empty">Not synced yet.</p>}
        </div>
        <div>
          <span className="combined-signal__label">From LeetCode</span>
          {practicedTopics.length > 0 ? (
            <div className="combined-signal__pills">
              {practicedTopics.map((t) => <span key={t} className="combined-signal__pill">{t}</span>)}
            </div>
          ) : <p className="combined-signal__empty">Not synced yet.</p>}
        </div>
      </div>

      {github && practicedTopics.length > 0 && (
        <p className="combined-signal__note">
          Together, these point toward someone who can both build ({languages[0] || 'your stack'}) and reason
          about algorithms ({practicedTopics[0]}) — worth pairing explicitly in interview prep and on your resume.
        </p>
      )}
    </section>
  )
}

export default CombinedSignal