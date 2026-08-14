// frontend/src/components/interview/CorrectionInput.jsx
import { useState } from 'react'
import './CorrectionInput.css'

function CorrectionInput({ onSubmit, onCancel, pending }) {
  const [value, setValue] = useState('')

  function handleSubmit(e) {
    e.preventDefault()
    if (!value.trim() || pending) return
    onSubmit(value.trim())
  }

  return (
    <form className="correction-input" onSubmit={handleSubmit}>
      <p className="correction-input__label">What was wrong?</p>
      <textarea
        rows={2}
        autoFocus
        placeholder="e.g. I wasn't the lead, I was one of three developers on that team..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        disabled={pending}
      />
      <div className="correction-input__actions">
        <button type="button" className="correction-input__cancel" onClick={onCancel} disabled={pending}>
          Cancel
        </button>
        <button type="submit" className="correction-input__submit" disabled={!value.trim() || pending}>
          {pending ? 'Regenerating…' : 'Submit correction'}
        </button>
      </div>
    </form>
  )
}

export default CorrectionInput