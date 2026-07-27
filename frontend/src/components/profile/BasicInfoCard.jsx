import { useState } from 'react'
import Card from '../common/Card'
import { IconUser } from '../icons/Icons'
import './ProfileSectionCard.css'

const FIELD_DISPLAY = [
  { label: 'Name', key: 'name', defaultValue: 'You' },
  { label: 'Location preference', key: 'location', defaultValue: 'Not set' },
  { label: 'Target roles', key: 'target_roles', defaultValue: 'Not set' },
  { label: 'Target companies', key: 'target_companies', defaultValue: 'Open' },
]

function BasicInfoCard({ user, results }) {
  const goal = results?.goal

  const fields = {
    name: user ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'You' : 'You',
    location: user?.location_pref || goal?.location || null,
    target_roles: user?.target_roles?.join(', ') || goal?.role || null,
    target_companies: user?.target_companies?.join(', ') || goal?.company || 'Open',
  }

  return (
    <Card className="psc">
      <div className="psc__header">
        <div className="psc__title-row">
          <span className="psc__icon"><IconUser size={16} /></span>
          <h3 className="psc__title">Basic info</h3>
        </div>
      </div>

      <div className="basic-info__grid">
        {FIELD_DISPLAY.map((f) => (
          <div key={f.key} className="basic-info__field">
            <div className="basic-info__field-label">{f.label}</div>
            <div className="basic-info__field-value">
              {fields[f.key] || f.defaultValue}
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}

export default BasicInfoCard
