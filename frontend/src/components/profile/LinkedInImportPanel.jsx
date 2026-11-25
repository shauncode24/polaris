import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { getLinkedInWorkspace, ingestLinkedInProfile } from '../../api/linkedin'
import './LinkedInImportPanel.css'

function LinkedInImportPanel({ onImported }) {
  const { token } = useAuth()
  const [rawText, setRawText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [workspace, setWorkspace] = useState(null)

  const loadWorkspace = useCallback(() => {
    getLinkedInWorkspace(token).then(setWorkspace).catch(() => setWorkspace(null))
  }, [token])

  useEffect(() => { loadWorkspace() }, [loadWorkspace])

  async function handleSubmit() {
    if (!rawText.trim()) {
      setError('Paste your LinkedIn profile text first — Headline, About, Experience, Education, and Skills sections all help.')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const data = await ingestLinkedInProfile(token, rawText.trim())
      setResult(data)
      setRawText('')
      loadWorkspace()
      onImported?.(data)
    } catch (err) {
      setError(err.message || 'Could not import your LinkedIn profile.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="li-import">
      <div className="li-import__header">
        <h2>Import LinkedIn</h2>
        <p className="li-import__lead">
          Copy your profile's Headline, About, Experience, Education, and Skills sections from LinkedIn
          and paste them below. Polaris never scrapes LinkedIn — this only reads what you paste here.
        </p>
      </div>

      {workspace?.has_data && (
        <p className="li-import__lead">
          Last imported {new Date(workspace.created_at).toLocaleDateString()}
          {workspace.headline ? ` — “${workspace.headline}”` : ''}: {workspace.experience_count} experience
          {workspace.experience_count === 1 ? '' : 's'}, {workspace.education_count} education
          {workspace.education_count === 1 ? ' entry' : ' entries'}, {workspace.skills.length} skill
          {workspace.skills.length === 1 ? '' : 's'}.
        </p>
      )}

      <textarea
        className="li-import__textarea"
        rows={10}
        placeholder="Paste your LinkedIn profile text here…"
        value={rawText}
        onChange={(e) => setRawText(e.target.value)}
        disabled={loading}
      />

      {error && <p className="li-import__error">{error}</p>}

      {result && (
        <div className="li-import__result">
          <p>
            Imported {result.experiences_created} new experience{result.experiences_created === 1 ? '' : 's'}
            {result.experiences_deduped > 0 ? ` (${result.experiences_deduped} already on file)` : ''},{' '}
            {result.education_created} education entr{result.education_created === 1 ? 'y' : 'ies'}, and{' '}
            {result.skills_processed} skill{result.skills_processed === 1 ? '' : 's'} as new evidence.
          </p>
        </div>
      )}

      <button type="button" className="li-import__submit" onClick={handleSubmit} disabled={loading}>
        {loading ? 'Importing…' : 'Import LinkedIn profile'}
      </button>
    </div>
  )
}

export default LinkedInImportPanel