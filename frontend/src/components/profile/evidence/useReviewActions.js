import { useState } from 'react'

// State for one card's confirm / edit / hide controls. `onReview(kind, id,
// action, fields)` performs the request and resolves once the record in the
// page has been updated; it rejects with an Error whose message is shown.
export function useReviewActions(kind, onReview) {
  const [editingId, setEditingId] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  async function run(id, action, fields = null) {
    setBusyId(id)
    setError('')
    try {
      await onReview(kind, id, action, fields)
      if (action === 'edit') setEditingId(null)
      return true
    } catch (err) {
      setError(err.message || 'That change could not be saved.')
      return false
    } finally {
      setBusyId(null)
    }
  }

  return { editingId, setEditingId, busyId, error, setError, run }
}
