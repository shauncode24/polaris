import { useState } from 'react'
import './InterviewSidebar.css'

function InterviewSidebar({ targetRole, targetCompany, questionsAsked, storiesUsed, competencies }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside className={`interview-sidebar ${collapsed ? 'interview-sidebar--collapsed' : ''}`}>
      <button type="button" className="interview-sidebar__toggle" onClick={() => setCollapsed((v) => !v)}>
        {collapsed ? '‹' : '›'}
      </button>

      {!collapsed && (
        <>
          <div className="interview-sidebar__section">
            <h3>Session</h3>
            <dl>
              <div><dt>Questions asked</dt><dd>{questionsAsked}</dd></div>
              {targetRole && <div><dt>Target role</dt><dd>{targetRole}</dd></div>}
              {targetCompany && <div><dt>Target company</dt><dd>{targetCompany}</dd></div>}
            </dl>
          </div>

          <div className="interview-sidebar__section">
            <h3>Stories used <span>{storiesUsed.length}</span></h3>
            {storiesUsed.length === 0 ? (
              <p className="interview-sidebar__empty">None yet.</p>
            ) : (
              <ul className="interview-sidebar__list">
                {storiesUsed.map((s) => <li key={s}>{s}</li>)}
              </ul>
            )}
          </div>

          <div className="interview-sidebar__section">
            <h3>Competencies covered <span>{competencies.length}</span></h3>
            {competencies.length === 0 ? (
              <p className="interview-sidebar__empty">None yet.</p>
            ) : (
              <div className="interview-sidebar__pills">
                {competencies.map((c) => <span key={c} className="pill">{c}</span>)}
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  )
}

export default InterviewSidebar