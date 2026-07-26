import './UserProfileCard.css'

function initials(firstName, lastName) {
  const f = firstName?.[0] || ''
  const l = lastName?.[0] || ''
  return (f + l).toUpperCase() || '?'
}

function UserProfileCard({ user }) {
  return (
    <div className="user-card">
      <div className="user-card__avatar">
        {user.avatar_url ? (
          <img src={user.avatar_url} alt={user.first_name} />
        ) : (
          <span>{initials(user.first_name, user.last_name)}</span>
        )}
      </div>
      <div className="user-card__details">
        <h2 className="user-card__name">{[user.first_name, user.last_name].filter(Boolean).join(' ')}</h2>
        <p className="user-card__email">{user.email || 'No email on file'}</p>
        <span className="user-card__provider">
          Signed in with {user.auth_provider === 'google' ? 'Google' : 'email &amp; password'}
        </span>
      </div>
    </div>
  )
}

export default UserProfileCard