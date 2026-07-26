import { useAuth } from '../contexts/AuthContext'
import HomeHeader from '../components/HomeHeader'
import UserProfileCard from '../components/UserProfileCard'
import './HomePage.css'

function HomePage() {
  const { user } = useAuth()

  if (!user) return null

  return (
    <div className="home-page">
      <div className="container">
        <HomeHeader />
        <main className="home-page__main">
          <h1 className="home-page__greeting">Welcome, {user.first_name}.</h1>
          <UserProfileCard user={user} />
        </main>
      </div>
    </div>
  )
}

export default HomePage