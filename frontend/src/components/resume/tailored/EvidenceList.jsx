// What a line, entry or skill is based on. `original` is the line's wording,
// given only for lines, to show whether the source still says it.

export function sourceKey(ref) {
  return `${ref.kind}:${ref.id ?? ''}:${ref.bullet ?? ''}`
}

function Detail({ item, source, original }) {
  if (!item.available) {
    return <p className="tr-evidence__warning">This has been removed or hidden since the resume was made.</p>
  }
  if (source.bullet == null || original == null) {
    return item.detail ? <p className="tr-evidence__detail">{item.detail}</p> : null
  }
  if (item.detail == null) {
    return <p className="tr-evidence__warning">That bullet is no longer there.</p>
  }
  if (item.detail === original.trim()) {
    return <p className="tr-evidence__detail">“{item.detail}”</p>
  }
  return <p className="tr-evidence__warning">This bullet has changed. It now reads: “{item.detail}”</p>
}

export default function EvidenceList({ sources, evidence, original = null }) {
  return (
    <ul className="tr-evidence">
      {sources.map((source) => {
        const item = evidence[sourceKey(source)]
        if (!item) return null
        return (
          <li key={sourceKey(source)}>
            <div className="tr-evidence__head">
              <span className="tr-evidence__origin">{item.origin}</span>
              <strong>{item.title}</strong>
              {item.url && /^https?:\/\//i.test(item.url) && (
                <a href={item.url} target="_blank" rel="noreferrer">Open</a>
              )}
            </div>
            <Detail item={item} source={source} original={original} />
          </li>
        )
      })}
    </ul>
  )
}
