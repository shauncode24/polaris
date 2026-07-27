// frontend/src/components/career/GoalManagementPanel.jsx
import { useState } from 'react'
import Button from '../common/Button'
import './GoalManagementPanel.css'

function EditGoalForm({ goal, onCancel, onSave }) {
  const [title, setTitle] = useState(goal.title)
  const [deadline, setDeadline] = useState(goal.deadline || '')
  const [priority, setPriority] = useState(goal.priority || '')
  const [saving, setSaving] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await onSave({ title, deadline: deadline || null, priority: priority || null })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="goal-mgmt__edit-form">
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Goal title" />
      <div className="goal-mgmt__edit-row">
        <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="">No priority</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
      </div>
      <div className="goal-mgmt__edit-actions">
        <button type="button" className="goal-mgmt__cancel" onClick={onCancel}>Cancel</button>
        <button type="button" className="goal-mgmt__confirm" disabled={saving || !title.trim()} onClick={handleSave}>
          {saving ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  )
}

function GoalManagementPanel({ goals, activeGoalId, onViewPlan, onUpdateGoal, onDeleteGoal, onNewGoal }) {
  const [editingId, setEditingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  async function handleDelete(id) {
    if (!window.confirm('Delete this goal? This cannot be undone.')) return
    setDeletingId(id)
    try {
      await onDeleteGoal(id)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <section className="goal-mgmt">
      <div className="goal-mgmt__header">
        <div>
          <h2>Goal management</h2>
          <p>Keep your active career bets intentional.</p>
        </div>
        <Button variant="outline" size="sm" onClick={onNewGoal}>+ New goal</Button>
      </div>

      {goals.length === 0 ? (
        <p className="goal-mgmt__empty">No goals yet.</p>
      ) : (
        <ul className="goal-mgmt__list">
          {goals.map((g) => (
            <li key={g.id} className="goal-mgmt__row">
              {editingId === g.id ? (
                <EditGoalForm
                  goal={g}
                  onCancel={() => setEditingId(null)}
                  onSave={async (payload) => {
                    await onUpdateGoal(g.id, payload)
                    setEditingId(null)
                  }}
                />
              ) : (
                <>
                  <div className="goal-mgmt__row-main">
                    <div className="goal-mgmt__row-title-line">
                      <span className="goal-mgmt__row-title">{g.title}</span>
                      {g.id === activeGoalId && <span className="goal-mgmt__badge goal-mgmt__badge--active">Active</span>}
                    </div>
                    <div className="goal-mgmt__row-meta">
                      <span>{Math.round(g.status_pct || 0)}% complete</span>
                      {g.deadline && <span>· Due {g.deadline}</span>}
                      {g.priority && (
                        <span className={`goal-mgmt__priority goal-mgmt__priority--${g.priority.toLowerCase()}`}>{g.priority}</span>
                      )}
                    </div>
                  </div>
                  <div className="goal-mgmt__row-actions">
                    <button type="button" className="goal-mgmt__view" onClick={() => onViewPlan(g.id)}>View plan</button>
                    <button type="button" className="goal-mgmt__icon-btn" aria-label="Edit goal" onClick={() => setEditingId(g.id)}>
                      ✎
                    </button>
                    <button
                      type="button"
                      className="goal-mgmt__icon-btn goal-mgmt__icon-btn--danger"
                      aria-label="Delete goal"
                      onClick={() => handleDelete(g.id)}
                      disabled={deletingId === g.id}
                    >
                      🗑
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export default GoalManagementPanel