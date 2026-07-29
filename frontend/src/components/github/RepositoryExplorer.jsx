import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatRelativeTime } from '../../utils/formatRelativeTime'
import './RepositoryExplorer.css'

function scoreTone(score) {
  if (score >= 80) return 'high'
  if (score >= 55) return 'medium'
  return 'low'
}

function collaborationLabel(mode) {
  if (mode === 'collaborative') return 'Collaborative'
  if (mode === 'mixed') return 'Mixed'
  return 'Solo'
}

function architectureLabel(depthLabel) {
  const map = {
    flat_script: 'Flat script',
    basic_structure: 'Basic structure',
    layered: 'Layered',
    well_architected: 'Well architected',
  }
  return map[depthLabel] || null
}

function RepositoryExplorer({ repositories }) {
  const [query, setQuery] = useState('')
  const [expandedRepos, setExpandedRepos] = useState(new Set())

  function toggleRepo(name) {
    const next = new Set(expandedRepos)
    if (next.has(name)) {
      next.delete(name)
    } else {
      next.add(name)
    }
    setExpandedRepos(next)
  }

  const filtered = useMemo(() => {
    const sorted = [...repositories].sort(
      (a, b) => new Date(b.pushed_at || 0) - new Date(a.pushed_at || 0)
    )
    const q = query.trim().toLowerCase()
    if (!q) return sorted
    return sorted.filter((r) =>
      [r.name, r.description, ...(r.languages || []), ...(r.topics || [])]
        .filter(Boolean)
        .some((v) => v.toLowerCase().includes(q))
    )
  }, [repositories, query])

  return (
    <section className="gh-explorer">
      <div className="gh-explorer__header">
        <div>
          <h2>Repository explorer</h2>
          <p>Raw repositories, translated into portfolio evidence.</p>
        </div>
        <input
          className="gh-explorer__search"
          type="text"
          placeholder="Search repositories"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {filtered.length === 0 ? (
        <p className="gh-explorer__empty">No repositories match your search.</p>
      ) : (
        <ul className="gh-explorer__list">
          {filtered.map((repo) => {
            const score = repo.project_score?.overall ?? 0
            const pills = [...(repo.languages || []), ...(repo.topics || [])]
            const nonContributedFork = repo.is_fork && repo.is_meaningful_fork_contribution === false
            const collabMode = repo.collaboration?.mode
            const archLabel = architectureLabel(repo.architecture_assessment?.depth_label)
            const isExpanded = expandedRepos.has(repo.name)

            return (
              <li key={repo.name} className="gh-repo-item">
                <div className="gh-repo-item__top" onClick={() => toggleRepo(repo.name)} style={{ cursor: 'pointer' }}>
                  <span className="gh-repo-item__name">{repo.name}</span>
                  <span className={`gh-repo-item__visibility ${repo.private ? 'is-private' : 'is-public'}`}>
                    {repo.private ? 'Private' : 'Public'}
                  </span>
                  {repo.archived && <span className="gh-repo-item__archived">Archived</span>}
                  {repo.is_fork && (
                    <span className="gh-repo-item__fork" title={nonContributedFork ? 'No significant original commits detected' : 'Fork with real original contribution'}>
                      {nonContributedFork ? 'Fork · no contribution' : 'Fork · contributed'}
                    </span>
                  )}
                  <span className={`gh-repo-item__score gh-repo-item__score--${scoreTone(score)}`}>{score}</span>
                  <button className="gh-repo-item__toggle-btn" aria-label="Toggle details">
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      style={{
                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 0.15s ease',
                      }}
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                  <span className="gh-repo-item__updated">Updated {formatRelativeTime(repo.pushed_at)}</span>
                </div>
                {repo.description && <p className="gh-repo-item__desc">{repo.description}</p>}

                <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                  <p className="gh-repo-item__headline" style={{ margin: 0 }}>
                    {(repo.headline || '').includes('no tests') ? (
                      <>
                        {(repo.headline || '').split('no tests')[0]}
                        <Link to="/career-planner?prefill=Testing" className="gh-repo-item__headline-link" title="Prefill focus topic in Career Planner">
                          no tests <small className="heuristic-tag" style={{ fontSize: '9px', opacity: 0.8 }}>heuristic ⓘ</small>
                        </Link>
                        {(repo.headline || '').split('no tests')[1]}
                      </>
                    ) : (
                      repo.headline
                    )}
                  </p>
                  {repo.tier && (
                    <span className={`gh-repo-item__tier gh-repo-item__tier--${repo.tier}`}>
                      {repo.tier === 'flagship' ? '★ Flagship' : repo.tier === 'career' ? 'Career project' : repo.tier === 'archived' ? 'Archived' : repo.tier === 'fork' ? 'Fork' : 'Experiment'}
                    </span>
                  )}
                  {!nonContributedFork && collabMode && (
                    <span className="gh-repo-item__signal-chip">
                      {collaborationLabel(collabMode)}
                    </span>
                  )}
                  {!nonContributedFork && archLabel && (
                    <span className="gh-repo-item__signal-chip">
                      {archLabel}
                    </span>
                  )}
                </div>

                {isExpanded && (
                  <div className="gh-repo-item__details">
                    {/* Architecture details */}
                    {!nonContributedFork && repo.architecture_assessment && (
                      <div className="gh-repo-item__details-section">
                        <div className="gh-repo-item__details-title">Architecture Assessment ({architectureLabel(repo.architecture_assessment.depth_label)})</div>
                        {repo.architecture_assessment.observations?.length > 0 ? (
                          <ul className="gh-repo-item__details-list">
                            {repo.architecture_assessment.observations.map((obs, index) => (
                              <li key={index} className="gh-repo-item__details-list-item">{obs}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="gh-repo-item__details-fallback">No observations generated.</p>
                        )}
                      </div>
                    )}

                    {/* Commit hygiene details */}
                    {repo.commit_hygiene && repo.commit_hygiene.sample_size > 0 && (
                      <div className="gh-repo-item__details-section">
                        <div className="gh-repo-item__details-title">Commit Message Hygiene (Score: {repo.commit_hygiene.score}/100)</div>
                        <div className="gh-repo-item__hygiene-stats">
                          <div className="gh-repo-item__hygiene-stat">
                            <span className="gh-repo-item__hygiene-stat-label">Conventional Commits</span>
                            <span className="gh-repo-item__hygiene-stat-val">{repo.commit_hygiene.conventional_pct}%</span>
                          </div>
                          <div className="gh-repo-item__hygiene-stat">
                            <span className="gh-repo-item__hygiene-stat-label">Generic Messages</span>
                            <span className="gh-repo-item__hygiene-stat-val">{repo.commit_hygiene.generic_pct}%</span>
                          </div>
                          <div className="gh-repo-item__hygiene-stat">
                            <span className="gh-repo-item__hygiene-stat-label">Avg message length</span>
                            <span className="gh-repo-item__hygiene-stat-val">{repo.commit_hygiene.avg_length} chars</span>
                          </div>
                          {repo.commit_hygiene.burst_detected && (
                            <div className="gh-repo-item__hygiene-alert">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                              Burst activity detected (commits dumped in a short window)
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Collaboration details */}
                    {repo.collaboration && repo.collaboration.pr_count > 0 && (
                      <div className="gh-repo-item__details-section">
                        <div className="gh-repo-item__details-title">Collaboration & Pull Requests (Score: {repo.collaboration.score}/100)</div>
                        <p className="gh-repo-item__details-text">
                          {repo.collaboration.pr_count} pull request(s) found.
                          {' '}{repo.collaboration.reviewed_pr_count} of them received peer review feedback.
                        </p>
                      </div>
                    )}

                    {/* Languages and topics */}
                    {pills.length > 0 && (
                      <div className="gh-repo-item__details-section">
                        <div className="gh-repo-item__details-title">Tech Stack & Tags</div>
                        <div className="gh-repo-item__pills">
                          {pills.map((pill) => (
                            <span key={pill} className="gh-repo-item__pill-tag">{pill}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

export default RepositoryExplorer