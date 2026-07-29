import { useEffect, useState } from 'react'
import InfoCard from '../common/InfoCard'
import { IconGithub } from '../icons/Icons'
import { getLinkSuggestions, confirmProjectLink } from '../../api/projects'
import { useAuth } from '../../contexts/AuthContext'
import './LinkSuggestionsPanel.css'

function LinkSuggestionsPanel({ onLinked }) {
  const { token } = useAuth()
  const [suggestions, setSuggestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const data = await getLinkSuggestions(token)
      setSuggestions(data.filter((s) => s.candidate_repo))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleConfirm(projectId, repoName) {
    setBusyId(projectId)
    try {
      await confirmProjectLink(token, projectId, repoName)
      setSuggestions((prev) => prev.filter((s) => s.project_id !== projectId))
      onLinked?.()
    } finally {
      setBusyId(null)
    }
  }

  if (loading || suggestions.length === 0) return null

  return (
    <InfoCard icon={IconGithub} iconTone="accent" title="Confirm GitHub links">
      <p className="link-suggestions__lead">
        These projects look like they match a synced repo — confirm to unlock full GitHub-verified scoring.
      </p>
      <div className="link-suggestions__list">
        {suggestions.map((s) => (
          <div className="link-suggestions__row" key={s.project_id}>
            <div>
              <strong>{s.project_name}</strong>
              <span className="link-suggestions__arrow"> → </span>
              <code>{s.candidate_repo}</code>
              <span className={`link-suggestions__badge link-suggestions__badge--${s.confidence}`}>
                {s.confidence}
              </span>
            </div>
            <button
              type="button"
              className="link-suggestions__confirm"
              disabled={busyId === s.project_id}
              onClick={() => handleConfirm(s.project_id, s.candidate_repo)}
            >
              {busyId === s.project_id ? 'Linking…' : 'Confirm'}
            </button>
          </div>
        ))}
      </div>
    </InfoCard>
  )
}

export default LinkSuggestionsPanel