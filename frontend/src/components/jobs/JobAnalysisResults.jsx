import { useState } from 'react'
import StickyActionBar from './StickyActionBar'
import './JobAnalysisResults.css'

function ConfidenceWord({ confidence, tier }) {
  const word = tier === 'have' ? (confidence >= 0.8 ? 'high' : 'medium') : (confidence >= 0.45 ? 'medium' : 'low')
  return <span className={`gap-conf gap-conf--${word}`}>{word}</span>
}

function barTierClass(pct) {
  if (pct >= 80) return 'cat-bar__fill--strong'
  if (pct >= 60) return 'cat-bar__fill--good'
  if (pct >= 40) return 'cat-bar__fill--partial'
  return 'cat-bar__fill--weak'
}

function HaveItem({ item }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <li className="gap-item">
      <div className="gap-item__row">
        <span className="gap-item__name">{item.skill.replace(/_/g, ' ')}</span>
        <ConfidenceWord confidence={item.confidence} tier="have" />
      </div>
      {item.explanation && <p className="gap-item__desc">{item.explanation}</p>}
      {item.evidence?.length > 0 && (
        <button type="button" className="gap-item__toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Hide evidence' : `${item.evidence.length} piece${item.evidence.length === 1 ? '' : 's'} of evidence`}
        </button>
      )}
      {expanded && (
        <ul className="gap-item__evidence">
          {item.evidence.map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      )}
    </li>
  )
}

function PartialItem({ item }) {
  return (
    <li className="gap-item">
      <div className="gap-item__row">
        <span className="gap-item__name">{item.skill.replace(/_/g, ' ')}</span>
        <ConfidenceWord confidence={item.confidence} tier="partial" />
      </div>
      {item.explanation && <p className="gap-item__desc">{item.explanation}</p>}
    </li>
  )
}

function MissingItem({ item }) {
  return (
    <li className="gap-item">
      <div className="gap-item__row">
        <span className="gap-item__name">{item.skill.replace(/_/g, ' ')}</span>
      </div>
      {item.unmatched_explanation && <p className="gap-item__desc">{item.unmatched_explanation}</p>}
      {item.estimated_weeks > 0 && (
        <span className="gap-item__weeks">~{item.estimated_weeks} week{item.estimated_weeks === 1 ? '' : 's'} to close</span>
      )}
    </li>
  )
}

function JobAnalysisResults({ data, jobId, roleLabel }) {
  const [showRaw, setShowRaw] = useState(false)
  const { report, category_breakdown: categories, overall_match: match, analysis, analysis_degraded: degraded } = data

  return (
    <div className="job-results">
      {degraded && (
        <p className="job-results__degraded-notice">
          The narrative portion of this report used a simplified fallback — the underlying skill data is still accurate.
        </p>
      )}

      <div className="job-results__top-grid">
        <div className="job-results__match-card">
          <span className="job-results__match-label">Overall match</span>
          <span className="job-results__match-value">{Math.round(match.percentage)}%</span>
          <span className={`job-results__match-tag job-results__match-tag--${match.percentage >= 75 ? 'strong' : match.percentage >= 50 ? 'good' : 'weak'}`}>
            <span className="job-results__match-dot" /> {match.label}
          </span>
        </div>

        <div className="job-results__stats-card">
          <div className="job-results__stats-row">
            <div className="job-results__stat">
              <strong>{match.matched_requirements}</strong>
              <span>Requirements matched</span>
            </div>
            <div className="job-results__stat">
              <strong>{match.required_matched}</strong>
              <span>Required skills</span>
            </div>
            <div className="job-results__stat">
              <strong>{match.nice_to_have_matched}</strong>
              <span>Nice-to-haves</span>
            </div>
          </div>
          {match.opportunity_narrative && (
            <p className="job-results__opportunity">↗ {match.opportunity_narrative}</p>
          )}
        </div>
      </div>

      {analysis.executive_summary && (
        <div className="job-results__card">
          <h2>Executive summary</h2>
          <p className="job-results__card-lead">Would a hiring manager interview you?</p>
          <p>{analysis.executive_summary}</p>
          {analysis.role_focus?.length > 0 && (
            <div className="job-results__tag-list">
              {analysis.role_focus.map((f) => <span key={f} className="job-results__tag">{f}</span>)}
            </div>
          )}
        </div>
      )}

      {categories?.length > 0 && (
        <div className="job-results__card">
          <h2>Category breakdown</h2>
          <p className="job-results__card-lead">Select a category to filter the skills below</p>
          <div className="cat-bar-list">
            {categories.map((c) => {
              const pct = Math.round(c.score * 100)
              return (
                <div className="cat-bar" key={c.category}>
                  <span className="cat-bar__label">{c.category}</span>
                  <div className="cat-bar__track">
                    <div className={`cat-bar__fill ${barTierClass(pct)}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className="cat-bar__pct">{pct}%</span>
                  <span className="cat-bar__matched">{c.matched_skills} matched</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      <div className="job-results__card">
        <h2>Skill gaps</h2>
        <div className="gap-columns">
          <div className="gap-column gap-column--have">
            <h3><span className="gap-dot gap-dot--have" /> Have <span className="gap-count">{report.have.length}</span></h3>
            {report.have.length === 0 ? (
              <p className="gap-empty">No confidently verified skills matched this role yet.</p>
            ) : (
              <ul>{report.have.map((h) => <HaveItem key={h.skill} item={h} />)}</ul>
            )}
          </div>
          <div className="gap-column gap-column--partial">
            <h3><span className="gap-dot gap-dot--partial" /> Partial <span className="gap-count">{report.partial.length}</span></h3>
            {report.partial.length === 0 ? (
              <p className="gap-empty">No partially-evidenced skills.</p>
            ) : (
              <ul>{report.partial.map((p) => <PartialItem key={p.skill} item={p} />)}</ul>
            )}
          </div>
          <div className="gap-column gap-column--missing">
            <h3><span className="gap-dot gap-dot--missing" /> Missing <span className="gap-count">{report.missing.length}</span></h3>
            {report.missing.length === 0 ? (
              <p className="gap-empty">Nothing missing — full coverage.</p>
            ) : (
              <ul>{report.missing.map((m) => <MissingItem key={m.skill} item={m} />)}</ul>
            )}
          </div>
        </div>
      </div>

      <div className="job-results__grid-2">
        {analysis.strengths?.length > 0 && (
          <div className="job-results__card">
            <h2>Strengths</h2>
            <ul className="job-results__check-list">
              {analysis.strengths.map((s, i) => <li key={i}>✓ {s}</li>)}
            </ul>
          </div>
        )}
        {analysis.risks?.length > 0 && (
          <div className="job-results__card">
            <h2>Risks</h2>
            <ul className="job-results__warn-list">
              {analysis.risks.map((r, i) => <li key={i}>⚠ {r}</li>)}
            </ul>
          </div>
        )}
      </div>

      {analysis.hiring_perspective && (
        <div className="job-results__card">
          <h2>Hiring perspective</h2>
          <p>{analysis.hiring_perspective}</p>
        </div>
      )}

      {analysis.learning_plan?.length > 0 && (
        <div className="job-results__card">
          <h2>Learning plan</h2>
          <p className="job-results__card-lead">Ordered by impact on your match</p>
          <ol className="learning-plan">
            {analysis.learning_plan.map((item, i) => (
              <li key={`${item.skill}-${i}`} className="learning-plan__item">
                <span className="learning-plan__index">{i + 1}</span>
                <div className="learning-plan__body">
                  <div className="learning-plan__header">
                    <span className="learning-plan__skill">{item.skill.replace(/_/g, ' ')}</span>
                    {item.phase && <span className="learning-plan__phase">{item.phase}</span>}
                  </div>
                  {item.rationale && <p className="learning-plan__rationale">{item.rationale}</p>}
                  <a
                    className="learning-plan__cta"
                    href={jobId ? `/career-planner?jobId=${jobId}` : '/career-planner'}
                  >
                    Add to a Career Plan →
                  </a>
                </div>
                <span className="learning-plan__weeks">{item.weeks}w</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {analysis.resume_advice?.length > 0 && (
        <div className="job-results__card">
          <h2>Resume advice</h2>
          <p className="job-results__card-lead">Evidence-aware edits to strengthen your application</p>
          <ul className="resume-advice">
            {analysis.resume_advice.map((a, i) => (
              <li key={i} className="resume-advice__row">
                <span>{a}</span>
                <a href="/profile" className="resume-advice__link">Edit in Resume →</a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {analysis.interview_focus?.length > 0 && (
        <div className="job-results__card">
          <h2>Interview focus</h2>
          <p className="job-results__card-lead">Areas an interviewer will likely probe for this gap profile</p>
          <div className="job-results__tag-list">
            {analysis.interview_focus.map((a) => <span key={a} className="job-results__tag">{a.replace(/_/g, ' ')}</span>)}
          </div>
          <a href="/interview" className="job-results__inline-btn">Practice these in Interview Prep →</a>
        </div>
      )}

      {analysis.career_strategy && (
        <div className="job-results__card">
          <h2>Career strategy</h2>
          <p>{analysis.career_strategy}</p>
        </div>
      )}

      {analysis.next_steps?.length > 0 && (
        <div className="job-results__card">
          <h2>Next steps</h2>
          <ol className="job-results__numbered">
            {analysis.next_steps.map((s, i) => <li key={i}><span>{i + 1}</span>{s}</li>)}
          </ol>
        </div>
      )}

      <div className="job-results__card">
        <button type="button" className="job-results__raw-toggle" onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide raw JSON response' : 'Show raw JSON response'}
        </button>
        {showRaw && <pre className="job-results__raw-json">{JSON.stringify(data, null, 2)}</pre>}
      </div>

      <StickyActionBar roleLabel={roleLabel} jobId={jobId} />
    </div>
  )
}

export default JobAnalysisResults