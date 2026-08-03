// frontend/src/components/leetcode/CombinedSignal.jsx
// Redesigned as a compact evidence summary (Review §"Combined Signal") —
// two short columns + one strength line, distinct from the Engineering
// Quadrant (which answers "what kind of engineer am I?" not "what's here").
import { useProfileData } from '../../contexts/ProfileDataContext'
import './CombinedSignal.css'

function CombinedSignal({ topicMastery }) {
  const { results } = useProfileData()
  const github = results.github

  const practicedTopics = (topicMastery || [])
    .filter((t) => t.problems > 0)
    .sort((a, b) => b.problems - a.problems)
    .slice(0, 3)
    .map((t) => t.topic)

  const languages = (github?.summary?.languages_detected || [])
    .slice(0, 3)
    .map((l) => l.language || l)

  if (!github && practicedTopics.length === 0) return null

  return (
    <section className="lc-card combined-signal">
      <h3>Combined signal</h3>

      <div className="combined-signal__cols">
        <div>
          <span className="combined-signal__label">GitHub</span>
          {languages.length > 0 ? (
            <div className="combined-signal__pills">
              {languages.map((l) => <span key={l} className="combined-signal__pill">✓ {l}</span>)}
            </div>
          ) : <p className="combined-signal__empty">Not synced yet.</p>}
        </div>
        <div>
          <span className="combined-signal__label">LeetCode</span>
          {practicedTopics.length > 0 ? (
            <div className="combined-signal__pills">
              {practicedTopics.map((t) => <span key={t} className="combined-signal__pill">✓ {t}</span>)}
            </div>
          ) : <p className="combined-signal__empty">Not synced yet.</p>}
        </div>
      </div>

      {github && practicedTopics.length > 0 && (
        <p className="combined-signal__note">
          Combined strength: {languages[0] || 'your stack'} engineering + {practicedTopics[0]}.
        </p>
      )}
    </section>
  )
}

export default CombinedSignal