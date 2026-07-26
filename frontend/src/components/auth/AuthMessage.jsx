import './AuthMessage.css'

function AuthMessage({ tone = 'error', children }) {
  if (!children) return null
  return <div className={`auth-message auth-message--${tone}`}>{children}</div>
}

export default AuthMessage