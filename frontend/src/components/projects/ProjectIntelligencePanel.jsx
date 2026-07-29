import { useState } from 'react'
import InfoCard from '../common/InfoCard'
import Button from '../common/Button'
import { IconSparkle } from '../icons/DashboardIcons'
import { explainProject, compareProject } from '../../api/projects'
import { useAuth } from '../../contexts/AuthContext'
import './ProjectIntelligencePanel.css'

function ProjectIntelligencePanel({ project }) {
  const { token } = useAuth()
  const [mode, setMode] = useState('explain')
  const [framing, setFraming] = useState('')
  const [compareTarget, setCompareTarget] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)

  if (!project) return null

  async function handleRun() {
    setLoading(true)
    setError('')
    setResult(null)
    try {
      if (mode === 'explain') {
        const data = await explainProject(token, project.id, framing.trim() || 'general')
        setResult(data)
      } else {
        if (!compareTarget.trim()) {
          setError('Enter something to compare this project against.')
          setLoading(false)
          return
        }
        const data = await compareProject(token, project.id, compareTarget.trim())
        setResult(data)
      }
    } catch (err) {
      setError(err.message || 'Could not generate that right now.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <InfoCard icon={IconSparkle} iconTone="accent" title={`Project Intelligence — ${project.name}`}>
      <div className="project-intel__tabs">
        <button
          type="button"
          className={`project-intel__tab ${mode === 'explain' ? 'project-intel__tab--active' : ''}`}
          onClick={() => { setMode('explain'); setResult(null); setError('') }}
        >
          Explain
        </button>
        <button
          type="button"
          className={`project-intel__tab ${mode === 'compare' ? 'project-intel__tab--active' : ''}`}
          onClick={() => { setMode('compare'); setResult(null); setError('') }}
        >
          Compare
        </button>
      </div>

      {mode === 'explain' ? (
        <input
          className="project-intel__input"
          placeholder='Framing, e.g. "as if interviewing at Amazon" (optional)'
          value={framing}
          onChange={(e) => setFraming(e.target.value)}
        />
      ) : (
        <input
          className="project-intel__input"
          placeholder="Comparison target, e.g. Kong Gateway"
          value={compareTarget}
          onChange={(e) => setCompareTarget(e.target.value)}
        />
      )}

      <Button size="sm" onClick={handleRun} disabled={loading}>
        {loading ? 'Thinking…' : mode === 'explain' ? 'Explain project' : 'Compare project'}
      </Button>

      {error && <p className="project-intel__error">{error}</p>}

      {result && result.insufficient_context && (
        <p className="project-intel__error">{result.context_note}</p>
      )}

      {result && !result.insufficient_context && mode === 'explain' && (
        <div className="project-intel__result">
          <p className="project-intel__synthesis">{result.synthesis}</p>
          <p>{result.framing_response}</p>
          {result.strengths?.length > 0 && (
            <>
              <h4>Strengths</h4>
              <ul>{result.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
          {result.gaps?.length > 0 && (
            <>
              <h4>Likely follow-ups</h4>
              <ul>{result.gaps.map((g, i) => <li key={i}>{g}</li>)}</ul>
            </>
          )}
          {result.talking_points?.length > 0 && (
            <>
              <h4>Talking points</h4>
              <ul>{result.talking_points.map((t, i) => <li key={i}>{t}</li>)}</ul>
            </>
          )}
        </div>
      )}

      {result && !result.insufficient_context && mode === 'compare' && (
        <div className="project-intel__result">
          <p className="project-intel__synthesis">{result.comparison_summary}</p>
          {result.this_project_strengths?.length > 0 && (
            <>
              <h4>Where your project holds up</h4>
              <ul>{result.this_project_strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
          {result.comparison_target_strengths?.length > 0 && (
            <>
              <h4>Where {compareTarget} wins</h4>
              <ul>{result.comparison_target_strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
          <p><strong>Recommendation:</strong> {result.recommendation}</p>
        </div>
      )}
    </InfoCard>
  )
}

export default ProjectIntelligencePanel