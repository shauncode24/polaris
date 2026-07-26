import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import HomeHeader from '../components/HomeHeader'
import UserProfileCard from '../components/UserProfileCard'
import IngestionResultsPanel from '../components/profile/IngestionResultsPanel'
import Button from '../components/common/Button'
import './HomePage.css'

function HomePage() {
  const { user } = useAuth()
  const { results } = useProfileData()

  if (!user) return null

  const hasAnyProfileData = Boolean(results.resume || results.github || results.leetcode)

  return (
    <div className="home-page">
      <div className="container">
        <HomeHeader />
        <main className="home-page__main">
          <h1 className="home-page__greeting">Welcome, {user.first_name}.</h1>
          <UserProfileCard user={user} />

          <div className="home-page__profile-cta">
            <Button as={Link} to="/build-profile" variant="outline">
              {hasAnyProfileData ? 'Sync more data' : 'Build your profile'}
            </Button>
          </div>

          {hasAnyProfileData ? (
            <IngestionResultsPanel results={results} />
          ) : (
            <p className="home-page__empty-state">
              You haven't synced any data yet. Build your profile to unlock the Skill Gap Analyzer,
              Career Planner, and Interview Prep.
            </p>
          )}
        </main>
      </div>
    </div>
  )
}

export default HomePage