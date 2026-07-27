import './InterviewSetupBar.css'

function InterviewSetupBar({ targetRole, targetCompany, onChangeRole, onChangeCompany }) {
  return (
    <div className="interview-setup">
      <label>
        Target role <span className="interview-setup__optional">(optional)</span>
        <input
          type="text"
          value={targetRole}
          onChange={(e) => onChangeRole(e.target.value)}
          placeholder="e.g. AI Engineer"
        />
      </label>
      <label>
        Target company <span className="interview-setup__optional">(optional)</span>
        <input
          type="text"
          value={targetCompany}
          onChange={(e) => onChangeCompany(e.target.value)}
          placeholder="e.g. OpenAI"
        />
      </label>
    </div>
  )
}

export default InterviewSetupBar