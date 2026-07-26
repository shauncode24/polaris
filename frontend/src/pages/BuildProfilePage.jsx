import { useNavigate } from 'react-router-dom'
import { useProfileData } from '../contexts/ProfileDataContext'
import { IconCompass } from '../components/icons/Icons'
import ThemeToggle from '../components/auth/ThemeToggle'
import Button from '../components/common/Button'
import ProfileProgress from '../components/profile/ProfileProgress'
import ResumeUploadCard from '../components/profile/ResumeUploadCard'
import GithubSyncCard from '../components/profile/GithubSyncCard'
import LeetCodeSyncCard from '../components/profile/LeetCodeSyncCard'
import IngestionResultsPanel from '../components/profile/IngestionResultsPanel'
import './BuildProfilePage.css'

function BuildProfilePage() {
  const { results, setResult } = useProfileData()
  const navigate = useNavigate()

  const steps = [
    { label: 'Resume', done: Boolean(results.resume) },
    { label: 'GitHub', done: Boolean(results.github) },
    { label: 'LeetCode', done: Boolean(results.leetcode) },
  ]

  const canContinue = Boolean(results.resume) // resume is the only required source

  return (
    <div className="build-profile-page">
      <header className="build-profile-page__header">
        <span className="build-profile-page__brand">
          <IconCompass size={18} /> Polaris
        </span>
        <ThemeToggle />
      </header>

      <main className="build-profile-page__main">
        <h1>Build Your Profile</h1>
        <p className="build-profile-page__lead">
          Everything below helps Polaris understand your career and personalize your roadmap.
          Resume is required — GitHub and LeetCode are optional, but strongly recommended.
        </p>

        <ProfileProgress steps={steps} />

        <div className="build-profile-page__cards">
          <ResumeUploadCard result={results.resume} onSuccess={(data) => setResult('resume', data)} />
          <GithubSyncCard result={results.github} onSuccess={(data) => setResult('github', data)} />
          <LeetCodeSyncCard result={results.leetcode} onSuccess={(data) => setResult('leetcode', data)} />
        </div>

        <IngestionResultsPanel results={results} />

        <div className="build-profile-page__actions">
          <Button variant="outline" onClick={() => navigate('/home')}>
            Skip for now
          </Button>
          <Button variant="primary" disabled={!canContinue} onClick={() => navigate('/home')}>
            Continue to Dashboard
          </Button>
        </div>
      </main>
    </div>
  )
}

export default BuildProfilePage