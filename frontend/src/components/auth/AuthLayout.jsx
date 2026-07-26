import AuthImagePanel from './AuthImagePanel'
import ThemeToggle from './ThemeToggle'
import './AuthLayout.css'

function AuthLayout({ children }) {
  return (
    <div className="auth-layout">
      <div className="auth-layout__card">
        <AuthImagePanel />
        <div className="auth-layout__panel">
          <div className="auth-layout__panel-top">
            <ThemeToggle />
          </div>
          <div className="auth-layout__panel-content">{children}</div>
        </div>
      </div>
    </div>
  )
}

export default AuthLayout