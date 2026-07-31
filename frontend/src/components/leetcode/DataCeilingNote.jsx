import './DataCeilingNote.css'

function DataCeilingNote({ note }) {
  if (!note) return null
  return (
    <div className="dcn">
      <span className="dcn__label">What this data can't tell you</span>
      <p className="dcn__text">{note}</p>
    </div>
  )
}

export default DataCeilingNote