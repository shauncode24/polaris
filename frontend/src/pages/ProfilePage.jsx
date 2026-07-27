import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { uploadResume, getProfileData } from '../api/profile'
import Sidebar from '../components/layout/Sidebar'
import TopBar from '../components/layout/TopBar'
import ProfileCompletenessBar from '../components/profile/ProfileCompletenessBar'
import BasicInfoCard from '../components/profile/BasicInfoCard'
import SkillsEvidenceCard from '../components/profile/SkillsEvidenceCard'
import ResumeCard from '../components/profile/ResumeCard'
import ExperiencesCard from '../components/profile/ExperiencesCard'
import ProjectsCard from '../components/profile/ProjectsCard'
import EducationCard from '../components/profile/EducationCard'
import CertificatesCard from '../components/profile/CertificatesCard'
import GitHubSyncCard from '../components/profile/GitHubSyncCard'
import LeetCodeSyncCard from '../components/profile/LeetCodeSyncCard'
import NotesCard from '../components/profile/NotesCard'
import './ProfilePage.css'

function ProfilePage() {
  const { user, token } = useAuth()
  const { results, setResult } = useProfileData()
  const reuploadRef = useRef(null)

  // Detailed profile data fetched from the backend
  const [profileData, setProfileData] = useState(null)
  const [profileLoading, setProfileLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setProfileLoading(true)
    getProfileData(token)
      .then((data) => { if (!cancelled) setProfileData(data) })
      .catch(() => { if (!cancelled) setProfileData(null) })
      .finally(() => { if (!cancelled) setProfileLoading(false) })
    return () => { cancelled = true }
  }, [token])

  // Merge backend data into a unified results object the cards can consume
  const enrichedResults = {
    ...results,
    resume: results.resume
      ? {
          ...results.resume,
          experiences: profileData?.experiences || [],
          projects: profileData?.projects || [],
          education: profileData?.education || [],
        }
      : results.resume,
  }

  // Format last sync time
  const lastSnapshotLabel = results.resume ? 'just now' : 'never'

  async function handleReuploadResume(file) {
    if (!file) return
    try {
      const data = await uploadResume(file, token)
      setResult('resume', { ...data, filename: file.name })
      // Refresh profile data after upload
      const freshData = await getProfileData(token)
      setProfileData(freshData)
    } catch {
      // Errors handled within ResumeCard
    }
  }

  return (
    <div className="profile-layout">
      <Sidebar />
      <div className="profile-main">
        <TopBar section="Overview" page="My profile" notificationCount={2} />

        <div className="profile-content">
          {/* Page hero */}
          <div className="profile-hero">
            <div className="profile-hero__left">
              <p className="profile-hero__eyebrow">Everything Polaris knows about you</p>
              <h1 className="profile-hero__title">My Profile</h1>
              <p className="profile-hero__sub">
                Last profile snapshot: {lastSnapshotLabel} · Sources update as you sync
              </p>
            </div>
            <div className="profile-hero__actions">
              <input
                ref={reuploadRef}
                type="file"
                accept=".pdf,.docx"
                hidden
                onChange={(e) => handleReuploadResume(e.target.files?.[0])}
              />
              <button
                type="button"
                className="profile-hero__btn profile-hero__btn--outline"
                onClick={() => reuploadRef.current?.click()}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 15V4" /><path d="M7.5 8.5L12 4l4.5 4.5" />
                  <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
                </svg>
                Re-upload resume
              </button>
              <button type="button" className="profile-hero__btn profile-hero__btn--primary">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z" />
                </svg>
                Edit profile
              </button>
            </div>
          </div>

          {/* Completeness bar */}
          <ProfileCompletenessBar results={results} />

          {/* Two-column layout */}
          <div className="profile-columns">
            {/* Left column */}
            <div className="profile-col profile-col--left">
              <BasicInfoCard user={user} results={results} />
              <ResumeCard
                result={results.resume}
                onSuccess={(data) => {
                  setResult('resume', data)
                  // Refresh detail data after successful upload
                  getProfileData(token).then(setProfileData).catch(() => {})
                }}
              />
              <ExperiencesCard results={enrichedResults} loading={profileLoading} />
              <ProjectsCard results={enrichedResults} loading={profileLoading} />
              <EducationCard results={enrichedResults} loading={profileLoading} />
            </div>

            {/* Right column */}
            <div className="profile-col profile-col--right">
              <SkillsEvidenceCard results={enrichedResults} />
              <CertificatesCard
                certificates={results.certificates || []}
                onChange={(certs) => setResult('certificates', certs)}
              />
              <GitHubSyncCard
                result={results.github}
                onSuccess={(data) => setResult('github', data)}
              />
              <LeetCodeSyncCard
                result={results.leetcode}
                onSuccess={(data) => setResult('leetcode', data)}
              />
              <NotesCard />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfilePage
