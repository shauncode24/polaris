import './LanguageAnalytics.css'

function LanguageAnalytics({ languages }) {
  const totalBytes = languages.reduce((sum, l) => sum + (l.bytes || 0), 0)
  const rows = languages
    .map((l) => ({ ...l, pct: totalBytes > 0 ? Math.round((l.bytes / totalBytes) * 100) : 0 }))
    .sort((a, b) => b.pct - a.pct)
    .slice(0, 8)

  return (
    <section className="gh-langs">
      <h2>Language analytics</h2>
      {rows.length === 0 ? (
        <p className="gh-langs__empty">No language data synced yet.</p>
      ) : (
        <div className="gh-langs__list">
          {rows.map((l) => (
            <div key={l.language} className="gh-langs__row">
              <span className="gh-langs__name">{l.language}</span>
              <div className="gh-langs__track">
                <div className="gh-langs__fill" style={{ width: `${l.pct}%` }} />
              </div>
              <span className="gh-langs__pct">{l.pct}%</span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

export default LanguageAnalytics