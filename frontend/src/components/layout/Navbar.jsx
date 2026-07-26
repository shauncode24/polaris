import { Link } from 'react-router-dom'
import { IconCompass, IconArrowRight } from '../icons/Icons'
import Button from '../common/Button'
import './Navbar.css'

function Navbar() {
  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <Link className="navbar__brand" to="/">
          <span className="navbar__mark">
            <IconCompass size={18} />
          </span>
          Polaris
        </Link>

        <nav className="navbar__actions">
          <Link className="navbar__login" to="/login">Login</Link>
          <Button as={Link} to="/signup" size="sm" variant="primary" icon={<IconArrowRight size={16} />}>
            Enter
          </Button>
        </nav>
      </div>
    </header>
  )
}

export default Navbar