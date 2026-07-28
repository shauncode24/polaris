import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeTailoring.css'

export default function ResumeTailoring({ jobs = [], onFetch, data, loading, error }) {
  const [selectedJd, setSelectedJd] = useState('')

  function handleRun() {
    if (selectedJd) onFetch(selectedJd)
  }

  const rankedItems = data?.ranked_items ?? []
  const llm = data?.llm ?? {}
  const leadIds = new Set(llm.lead_items ?? [])
  const cutIds = new Set(llm.cut_bullets ?? [])
  const emphasizeIds = new Set(llm.emphasize_bullets ?? [])

  const hasData = !!data

  return (
    <CollapsibleSection title="Resume Tailoring" defaultOpen={false} className="rtail">
      <div className="rtail__body">
        {/* JD selector */}
        <div>
          <div className="rtail__section-label">Target Job Description</div>
          <div className="rtail__jd-row">
            <select
              className="rtail__jd-select"
              value={selectedJd}
              onChange={(e) => setSelectedJd(e.target.value)}
            >
              <option value="">— Select a job description —</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.role ? `${j.role}${j.company ? ` @ ${j.company}` : ''}` : j.company || j.id}
                </option>
              ))}
            </select>
            <button
              className="rtail__run-btn"
              onClick={handleRun}
              disabled={!selectedJd || loading}
            >
              {loading ? '…' : hasData ? 'Re-run' : 'Tailor'}
            </button>
          </div>
        </div>

        {jobs.length === 0 && (
          <div className="rtail__empty">No job descriptions yet — analyze a JD first.</div>
        )}

        {loading && <div className="rtail__loading">Generating tailoring recommendations…</div>}
        {error && <div className="rtail__error">{error}</div>}

        {hasData && !loading && (
          <>
            {/* Target role header */}
            {(data.role || data.company) && (
              <div>
                <div className="rtail__header-meta">
                  {data.role}{data.company ? ` @ ${data.company}` : ''}
                </div>
              </div>
            )}

            {/* Rationale */}
            {llm.rationale && (
              <div className="rtail__rationale">{llm.rationale}</div>
            )}

            {/* Ranked items */}
            {rankedItems.length > 0 && (
              <div>
                <div className="rtail__section-label">Ranked Relevance</div>
                <div className="rtail__items">
                  {rankedItems.slice(0, 8).map((item, i) => {
                    const isLead = leadIds.has(item.id)
                    return (
                      <div key={item.id} className={`rtail__item${isLead ? ' rtail__item--lead' : ''}`}>
                        <span className="rtail__item-rank">#{i + 1}</span>
                        <div className="rtail__item-info">
                          <div className="rtail__item-label">{item.label}</div>
                          <div className="rtail__item-type">{item.type}</div>
                          {item.matched_skills.length > 0 && (
                            <div className="rtail__item-skills">
                              {item.matched_skills.slice(0, 4).map((s) => (
                                <span key={s} className="rtail__skill-chip">{s}</span>
                              ))}
                            </div>
                          )}
                        </div>
                        <span className="rtail__item-score">{item.relevance_score.toFixed(1)}</span>
                        {isLead && <span className="rtail__item-lead-badge">Lead</span>}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Bullets to emphasize */}
            {emphasizeIds.size > 0 && (
              <div>
                <div className="rtail__section-label">Bullets to Emphasize ({emphasizeIds.size})</div>
                <div className="rtail__bullet-list">
                  {[...emphasizeIds].map((id) => (
                    <div key={id} className="rtail__bullet-row">
                      <span className="rtail__bullet-id">{id}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Bullets to cut */}
            {cutIds.size > 0 && (
              <div>
                <div className="rtail__section-label">Bullets to Consider Cutting ({cutIds.size})</div>
                <div className="rtail__bullet-list">
                  {[...cutIds].map((id) => (
                    <div key={id} className="rtail__bullet-row">
                      <span className="rtail__bullet-id">{id}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {data.analysis_degraded && (
              <div className="rtail__degraded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Tailoring analysis degraded — showing deterministic fallback.
              </div>
            )}
          </>
        )}
      </div>
    </CollapsibleSection>
  )
}
