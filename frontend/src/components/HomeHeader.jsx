import { IconCompass } from './icons/Icons'
import ThemeToggle from './auth/ThemeToggle'
import Button from './common/Button'
import { useAuth } from '../contexts/AuthContext'
import './HomeHeader.css'

function HomeHeader() {
  const { logout } = useAuth()

  return (
    <header className="home-header">
      <span className="home-header__brand">
        <IconCompass size={18} />
        Polaris
      </span>
      <div className="home-header__actions">
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={logout}>Log out</Button>
      </div>
    </header>
  )
}

export default HomeHeader