import './ProfileIngestion.css'

function IngestionResultsPanel({ results }) {
  const entries = Object.entries(results || {}).filter(([, value]) => value)
  if (entries.length === 0) return null

  return (
    <div className="ingestion-results">
      <h3>Raw sync output</h3>
      {entries.map(([key, value]) => (
        <details key={key} className="ingestion-results__block" open>
          <summary>{key}</summary>
          <pre>{JSON.stringify(value, null, 2)}</pre>
        </details>
      ))}
    </div>
  )
}

export default IngestionResultsPanel