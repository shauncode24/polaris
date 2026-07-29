import { useState } from 'react'
import CollapsibleSection from '../common/CollapsibleSection'
import './ResumeCoherence.css'

export default function ResumeCoherence({ token, onFetch, data, loading, error }) {
  const [targetRole, setTargetRole] = useState('')
  const hasData = !!data

  function handleRun() {
    // Second argument tells the API layer whether to force a fresh LLM
    // call (Re-run) or accept a cached report if one exists (Analyze).
    onFetch(targetRole.trim() || null, hasData)
  }

  const facts = data?.facts ?? {}
  const narrative = data?.narrative ?? {}
  const dilution = data?.dilution ?? {}

  const distribution = facts.category_distribution ?? {}
  const sortedDist = Object.entries(distribution).sort((a, b) => b[1] - a[1])
  const maxPct = sortedDist[0]?.[1] ?? 1

  const offNarrative = facts.off_narrative_bullets ?? []
  const weakBullets = dilution.weak_bullets ?? []

  return (
    <CollapsibleSection title="Narrative Coherence" defaultOpen={false} className="rcoh">
      <div className="rcoh__body">
        {/* Role input */}
        <div>
          <div className="rcoh__section-label">Target Role (optional)</div>
          <div className="rcoh__role-input-row">
            <input
              className="rcoh__role-input"
              type="text"
              placeholder="e.g. Backend Engineer"
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !loading && handleRun()}
            />
            <button className="rcoh__role-btn" onClick={handleRun} disabled={loading}>
              {loading ? '…' : hasData ? 'Re-run' : 'Analyze'}
            </button>
          </div>
        </div>

        {loading && <div className="rcoh__loading">Analyzing narrative coherence…</div>}
        {error && <div className="rcoh__error">{error}</div>}

        {hasData && !loading && (
          <>
            {/* Argued role */}
            {narrative.argued_role && (
              <div className="rcoh__argued-role">
                <span className="rcoh__argued-label">Argues for</span>
                <span className="rcoh__argued-val">{narrative.argued_role}</span>
                {facts.target_role_alignment_pct != null && (
                  <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-soft)' }}>
                    {facts.target_role_alignment_pct}% aligned
                  </span>
                )}
              </div>
            )}

            {/* Positioning statement */}
            {narrative.positioning_statement && (
              <div className="rcoh__positioning">{narrative.positioning_statement}</div>
            )}

            {/* Category distribution */}
            {sortedDist.length > 0 && (
              <div>
                <div className="rcoh__section-label">Skill Signal Distribution</div>
                <div className="rcoh__dist">
                  {sortedDist.map(([cat, pct]) => (
                    <div key={cat} className="rcoh__dist-row">
                      <span className="rcoh__dist-name">{cat}</span>
                      <div className="rcoh__dist-track">
                        <div className="rcoh__dist-fill" style={{ width: `${(pct / maxPct) * 100}%` }} />
                      </div>
                      <span className="rcoh__dist-pct">{pct}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Strengths */}
            {narrative.strengths_for_this_story?.length > 0 && (
              <div>
                <div className="rcoh__section-label">Strengths</div>
                <div className="rcoh__list">
                  {narrative.strengths_for_this_story.map((s, i) => (
                    <div key={i} className="rcoh__list-item">
                      <div className="rcoh__list-dot" />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Weakens */}
            {narrative.weakens_the_story?.length > 0 && (
              <div>
                <div className="rcoh__section-label">What Weakens the Story</div>
                <div className="rcoh__list">
                  {narrative.weakens_the_story.map((s, i) => (
                    <div key={i} className="rcoh__list-item">
                      <div className="rcoh__list-dot rcoh__list-dot--warn" />
                      {s}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Off-narrative bullets */}
            {offNarrative.length > 0 && (
              <div>
                <div className="rcoh__section-label">Off-Narrative Bullets ({offNarrative.length})</div>
                <div className="rcoh__offtable">
                  {offNarrative.slice(0, 6).map((b) => (
                    <div key={b.bullet_id} className="rcoh__offrow">
                      <span className="rcoh__offlabel">{b.source_label}</span>
                      <span className="rcoh__offcats">{b.categories.join(', ')}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Dilution summary */}
            {weakBullets.length > 0 && (
              <div>
                <div className="rcoh__section-label">Signal Dilution</div>
                <div className="rcoh__recommendation">
                  {dilution.recommendation}
                </div>
              </div>
            )}

            {/* Recommendation */}
            {narrative.recommendation && (
              <div>
                <div className="rcoh__section-label">Recommendation</div>
                <div className="rcoh__recommendation">{narrative.recommendation}</div>
              </div>
            )}

            {/* Degraded warning */}
            {data.analysis_degraded && (
              <div className="rcoh__degraded">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                Narrative analysis degraded — showing deterministic fallback.
              </div>
            )}
          </>
        )}
      </div>
    </CollapsibleSection>
  )
}