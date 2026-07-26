import { IconCompass, IconArrowRight } from '../icons/Icons'
import Button from '../common/Button'
import './Navbar.css'

function Navbar() {
  return (
    <header className="navbar">
      <div className="container navbar__inner">
        <a className="navbar__brand" href="#top">
          <span className="navbar__mark">
            <IconCompass size={18} />
          </span>
          Polaris
        </a>

        <nav className="navbar__actions">
          <a className="navbar__login" href="#login">Login</a>
          <Button as="a" href="#how-it-works" size="sm" variant="primary" icon={<IconArrowRight size={16} />}>
            Enter
          </Button>
        </nav>
      </div>
    </header>
  )
}

export default Navbar
