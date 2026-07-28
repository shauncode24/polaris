import { useMemo, useState } from 'react'
import { formatRelativeTime } from '../../utils/formatRelativeTime'
import './RepositoryExplorer.css'

function scoreTone(score) {
  if (score >= 80) return 'high'
  if (score >= 55) return 'medium'
  return 'low'
}

function RepositoryExplorer({ repositories }) {
  const [query, setQuery] = useState('')

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
            const pills = [...(repo.languages || []), ...(repo.topics || [])].slice(0, 4)
            return (
              <li key={repo.name} className="gh-repo-item">
                <div className="gh-repo-item__top">
                  <span className="gh-repo-item__name">{repo.name}</span>
                  <span className={`gh-repo-item__visibility ${repo.private ? 'is-private' : 'is-public'}`}>
                    {repo.private ? 'Private' : 'Public'}
                  </span>
                  {repo.archived && <span className="gh-repo-item__archived">Archived</span>}
                  <span className={`gh-repo-item__score gh-repo-item__score--${scoreTone(score)}`}>{score}</span>
                  <span className="gh-repo-item__updated">Updated {formatRelativeTime(repo.pushed_at)}</span>
                </div>
                {repo.description && <p className="gh-repo-item__desc">{repo.description}</p>}
                {pills.length > 0 && (
                  <div className="gh-repo-item__pills">
                    {pills.map((p) => (
                      <span key={p} className="gh-repo-item__pill">{p}</span>
                    ))}
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