import { Link } from 'react-router-dom'
import Badge from '../common/Badge'
import Button from '../common/Button'
import { IconArrowRight } from '../icons/Icons'
import './Hero.css'

function Hero() {
  return (
    <section className="hero" id="top">
      <div className="container hero__inner">
        <Badge>AI Career Operating System</Badge>

        <h1 className="hero__title">
          Your AI Career
          <span className="hero__title-script">Operating System</span>
        </h1>

        <p className="hero__lead">
          Upload your resume, sync your GitHub and LeetCode, analyze jobs, generate
          personalized roadmaps, and practice interviews — all from a single evolving profile.
        </p>

        <div className="hero__actions">
          <Button as={Link} to="/signup" variant="primary" icon={<IconArrowRight size={16} />}>
            Enter Polaris
          </Button>
          <Button as={Link} to="/login" variant="outline">
            Login
          </Button>
        </div>

        <p className="hero__note">Single-user local preview</p>
      </div>
    </section>
  )
}

export default Hero