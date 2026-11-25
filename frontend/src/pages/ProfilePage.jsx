import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useProfileData } from '../contexts/ProfileDataContext'
import { uploadResume, getProfileData, reviewEvidenceItem, setSkillVisibility } from '../api/profile'
import { confirmProjectLink, unlinkProject } from '../api/projects'
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
import LinkedInImportPanel from '../components/profile/LinkedInImportPanel'
import NotesCard from '../components/profile/NotesCard'
import './ProfilePage.css'

function ProfilePage() {
  const { user, token } = useAuth()
  const { results, setResult } = useProfileData()
  const reuploadRef = useRef(null)

  // The evidence record as the server holds it: what Polaris knows about
  // the user and where each item came from. Every card below reads this, not
  // browser-local state, so it is the same on every device and after every sync.
  const [evidence, setEvidence] = useState(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [loadError, setLoadError] = useState('')

  const refreshEvidence = useCallback(async () => {
    try {
      setEvidence(await getProfileData(token))
      setLoadError('')
    } catch (err) {
      setLoadError(err.message || 'Could not load your profile.')
    }
  }, [token])

  useEffect(() => {
    let cancelled = false
    setProfileLoading(true)
    refreshEvidence().finally(() => { if (!cancelled) setProfileLoading(false) })
    return () => { cancelled = true }
  }, [refreshEvidence])

  // Confirm / edit / hide one item, then swap the server's version into the page.
  async function handleReview(kind, id, action, fields) {
    const updated = await reviewEvidenceItem(token, kind, id, action, fields)
    setEvidence((current) => ({
      ...current,
      [kind]: current[kind].map((item) => (item.id === id ? updated : item)),
    }))
  }

  async function handleSkillVisibility(skill, hidden) {
    await setSkillVisibility(token, skill, hidden)
    await refreshEvidence()  // hiding or restoring changes confidence readings, so reload them
  }

  async function handleLinkProject(projectId, repoName) {
    await confirmProjectLink(token, projectId, repoName)
    await refreshEvidence()
  }

  async function handleDismissLink(projectId) {
    await unlinkProject(token, projectId)
    await refreshEvidence()
  }

  // Format last sync time
  const lastSnapshotLabel = results.resume ? 'just now' : 'never'

  async function handleReuploadResume(file) {
    if (!file) return
    try {
      const data = await uploadResume(file, token)
      setResult('resume', { ...data, filename: file.name })
      await refreshEvidence()
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
                  refreshEvidence()
                }}
              />
              {loadError && <p className="psc__error">{loadError}</p>}
              <ExperiencesCard
                experiences={evidence?.experiences}
                loading={profileLoading}
                onReview={handleReview}
              />
              <ProjectsCard
                projects={evidence?.projects}
                pendingLinks={evidence?.pending_repo_links}
                loading={profileLoading}
                onReview={handleReview}
                onLink={handleLinkProject}
                onDismissLink={handleDismissLink}
              />
              <EducationCard
                education={evidence?.education}
                loading={profileLoading}
                onReview={handleReview}
              />
            </div>

            {/* Right column */}
            <div className="profile-col profile-col--right">
              <SkillsEvidenceCard
                skills={evidence?.skills}
                loading={profileLoading}
                onSetVisibility={handleSkillVisibility}
              />
              <CertificatesCard
                certificates={results.certificates || []}
                onChange={(certs) => setResult('certificates', certs)}
              />
              <GitHubSyncCard
                result={results.github}
                onSuccess={(data) => {
                  setResult('github', data)
                  refreshEvidence()  // the sync adds GitHub-only projects
                }}
              />
              <LeetCodeSyncCard
                result={results.leetcode}
                onSuccess={(data) => setResult('leetcode', data)}
              />
              <LinkedInImportPanel onImported={refreshEvidence} />
              <NotesCard />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfilePage
