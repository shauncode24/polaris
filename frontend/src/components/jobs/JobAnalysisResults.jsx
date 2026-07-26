import { useState } from 'react'
import './JobAnalysisResults.css'

function ConfidencePill({ value }) {
  const pct = Math.round((value ?? 0) * 100)
  const tone = pct >= 60 ? 'strong' : pct >= 30 ? 'partial' : 'weak'
  return <span className={`confidence-pill confidence-pill--${tone}`}>{pct}%</span>
}

function SkillColumn({ title, tone, items, renderItem, emptyLabel }) {
  return (
    <div className={`skill-column skill-column--${tone}`}>
      <h3>{title} <span className="skill-column__count">{items.length}</span></h3>
      {items.length === 0 ? (
        <p className="skill-column__empty">{emptyLabel}</p>
      ) : (
        <ul>{items.map(renderItem)}</ul>
      )}
    </div>
  )
}

function JobAnalysisResults({ data }) {
  const [showRaw, setShowRaw] = useState(false)
  const {
    report,
    category_breakdown: categories,
    overall_match: match,
    analysis,
    analysis_degraded: degraded,
  } = data

  return (
    <section className="job-results">
      {degraded && (
        <p className="job-results__degraded-notice">
          The narrative portion of this report used a simplified fallback — the underlying skill data is still accurate.
        </p>
      )}

      <div className="job-results__overall">
        <div className="job-results__score">
          <span className="job-results__score-value">{Math.round(match.percentage)}%</span>
          <span className="job-results__score-label">{match.label}</span>
        </div>
        <div className="job-results__overall-stats">
          <div><strong>{match.matched_requirements}</strong><span>Matched requirements</span></div>
          <div><strong>{match.required_matched}</strong><span>Required skills</span></div>
          <div><strong>{match.nice_to_have_matched}</strong><span>Nice-to-haves</span></div>
        </div>
        {match.opportunity_narrative && <p className="job-results__opportunity">{match.opportunity_narrative}</p>}
      </div>

      {analysis.executive_summary && (
        <div className="job-results__card">
          <h2>Executive Summary</h2>
          <p>{analysis.executive_summary}</p>
          {analysis.role_focus?.length > 0 && (
            <ul className="job-results__tag-list">
              {analysis.role_focus.map((f) => <li key={f}>{f}</li>)}
            </ul>
          )}
        </div>
      )}

      {categories?.length > 0 && (
        <div className="job-results__card">
          <h2>Category Breakdown</h2>
          <div className="category-breakdown">
            {categories.map((c) => (
              <div className="category-breakdown__row" key={c.category}>
                <div className="category-breakdown__label">
                  <span>{c.category}</span>
                  <span className="category-breakdown__matched">{c.matched_skills}</span>
                </div>
                <div className="category-breakdown__bar">
                  <div className="category-breakdown__bar-fill" style={{ width: `${Math.round(c.score * 100)}%` }} />
                </div>
                <span className="category-breakdown__badge">{c.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="job-results__card">
        <h2>Skill Gap Analysis</h2>
        <div className="skill-columns">
          <SkillColumn
            title="Have"
            tone="have"
            items={report.have}
            emptyLabel="No confidently verified skills matched this role yet."
            renderItem={(s) => (
              <li key={s.skill}>
                <div className="skill-row">
                  <span className="skill-row__name">{s.skill.replace(/_/g, ' ')}</span>
                  <ConfidencePill value={s.confidence} />
                </div>
                {s.explanation && <p className="skill-row__detail">{s.explanation}</p>}
                {s.evidence?.length > 0 && (
                  <ul className="skill-row__evidence">
                    {s.evidence.map((e, i) => <li key={i}>{e}</li>)}
                  </ul>
                )}
              </li>
            )}
          />
          <SkillColumn
            title="Partial"
            tone="partial"
            items={report.partial}
            emptyLabel="No partially-evidenced skills."
            renderItem={(s) => (
              <li key={s.skill}>
                <div className="skill-row">
                  <span className="skill-row__name">{s.skill.replace(/_/g, ' ')}</span>
                  <ConfidencePill value={s.confidence} />
                </div>
                {s.explanation && <p className="skill-row__detail">{s.explanation}</p>}
              </li>
            )}
          />
          <SkillColumn
            title="Missing"
            tone="missing"
            items={report.missing}
            emptyLabel="Nothing missing — full coverage."
            renderItem={(s) => (
              <li key={s.skill}>
                <div className="skill-row">
                  <span className="skill-row__name">{s.skill.replace(/_/g, ' ')}</span>
                  {s.estimated_weeks > 0 && <span className="skill-row__weeks">{s.estimated_weeks}w</span>}
                </div>
                {s.unmatched_explanation && <p className="skill-row__detail">{s.unmatched_explanation}</p>}
              </li>
            )}
          />
        </div>
      </div>

      <div className="job-results__grid-2">
        {analysis.strengths?.length > 0 && (
          <div className="job-results__card">
            <h2>Strengths</h2>
            <ul className="job-results__bullets">{analysis.strengths.map((s, i) => <li key={i}>{s}</li>)}</ul>
          </div>
        )}
        {analysis.risks?.length > 0 && (
          <div className="job-results__card">
            <h2>Risks</h2>
            <ul className="job-results__bullets">{analysis.risks.map((r, i) => <li key={i}>{r}</li>)}</ul>
          </div>
        )}
      </div>

      {analysis.hiring_perspective && (
        <div className="job-results__card">
          <h2>Hiring Perspective</h2>
          <p>{analysis.hiring_perspective}</p>
        </div>
      )}

      <div className="job-results__grid-2">
        {analysis.resume_advice?.length > 0 && (
          <div className="job-results__card">
            <h2>Resume Advice</h2>
            <ul className="job-results__bullets">{analysis.resume_advice.map((a, i) => <li key={i}>{a}</li>)}</ul>
          </div>
        )}
        {analysis.interview_focus?.length > 0 && (
          <div className="job-results__card">
            <h2>Interview Focus</h2>
            <ul className="job-results__tag-list">
              {analysis.interview_focus.map((a) => <li key={a}>{a.replace(/_/g, ' ')}</li>)}
            </ul>
          </div>
        )}
      </div>

      {analysis.learning_plan?.length > 0 && (
        <div className="job-results__card">
          <h2>Learning Plan</h2>
          <ol className="learning-plan">
            {analysis.learning_plan.map((item, i) => (
              <li key={`${item.skill}-${i}`} className="learning-plan__item">
                <div className="learning-plan__header">
                  <span className="learning-plan__skill">{item.skill.replace(/_/g, ' ')}</span>
                  <span className="learning-plan__weeks">{item.weeks}w</span>
                </div>
                {item.phase && <span className="learning-plan__phase">{item.phase}</span>}
                {item.rationale && <p className="learning-plan__rationale">{item.rationale}</p>}
              </li>
            ))}
          </ol>
        </div>
      )}

      {analysis.career_strategy && (
        <div className="job-results__card">
          <h2>Career Strategy</h2>
          <p>{analysis.career_strategy}</p>
        </div>
      )}

      {analysis.next_steps?.length > 0 && (
        <div className="job-results__card">
          <h2>Next Steps</h2>
          <ol className="job-results__numbered">{analysis.next_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
        </div>
      )}

      <div className="job-results__card">
        <button type="button" className="job-results__raw-toggle" onClick={() => setShowRaw((v) => !v)}>
          {showRaw ? 'Hide raw JSON response' : 'Show raw JSON response'}
        </button>
        {showRaw && <pre className="job-results__raw-json">{JSON.stringify(data, null, 2)}</pre>}
      </div>
    </section>
  )
}

export default JobAnalysisResults