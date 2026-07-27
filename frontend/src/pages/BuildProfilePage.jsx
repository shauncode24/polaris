import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProfileData } from '../contexts/ProfileDataContext'
import OnboardingHeader from '../components/onboarding/OnboardingHeader'
import WelcomeStep from '../components/onboarding/WelcomeStep'
import ResumeStep from '../components/onboarding/ResumeStep'
import GithubStep from '../components/onboarding/GithubStep'
import LeetCodeStep from '../components/onboarding/LeetCodeStep'
import CertificatesStep from '../components/onboarding/CertificatesStep'
import GoalStep from '../components/onboarding/GoalStep'
import ReviewStep from '../components/onboarding/ReviewStep'
import './BuildProfilePage.css'

const STEP_LABELS = ['', 'Resume', 'GitHub', 'LeetCode', 'Certificates', 'Your goal', 'Review']

function BuildProfilePage() {
  const { results, setResult } = useProfileData()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [certificates, setCertificates] = useState(results.certificates || [])
  const [goal, setGoal] = useState(results.goal || null)

  function saveCertificates(next) {
    setCertificates(next)
    setResult('certificates', next)
  }

  function saveGoal(next) {
    setGoal(next)
    setResult('goal', next)
  }

  function handleSaveExit() {
    navigate('/home')
  }

  function goTo(n) {
    setStep(n)
  }

  if (step === 0) {
    return <WelcomeStep onStart={() => setStep(1)} onSaveExit={handleSaveExit} />
  }

  return (
    <div className="onb-page">
      <OnboardingHeader
        step={step}
        stepLabel={STEP_LABELS[step]}
        onBack={step > 1 ? () => setStep(step - 1) : null}
        onSaveExit={handleSaveExit}
      />

      <div className="onb-content">
        {step === 1 && (
          <ResumeStep
            result={results.resume}
            onSuccess={(data) => setResult('resume', data)}
            onContinue={() => goTo(2)}
          />
        )}
        {step === 2 && (
          <GithubStep
            result={results.github}
            onSuccess={(data) => setResult('github', data)}
            onContinue={() => goTo(3)}
            onSkip={() => goTo(3)}
          />
        )}
        {step === 3 && (
          <LeetCodeStep
            result={results.leetcode}
            onSuccess={(data) => setResult('leetcode', data)}
            onContinue={() => goTo(4)}
            onSkip={() => goTo(4)}
          />
        )}
        {step === 4 && (
          <CertificatesStep
            certificates={certificates}
            onChange={saveCertificates}
            onContinue={() => goTo(5)}
            onSkip={() => goTo(5)}
          />
        )}
        {step === 5 && (
          <GoalStep
            goal={goal}
            onSuccess={saveGoal}
            onContinue={() => goTo(6)}
            onSkip={() => goTo(6)}
          />
        )}
        {step === 6 && (
          <ReviewStep
            resume={results.resume}
            github={results.github}
            leetcode={results.leetcode}
            certificates={certificates}
            goal={goal}
            onEditStep={goTo}
            onFinish={() => navigate('/home')}
          />
        )}
      </div>
    </div>
  )
}

export default BuildProfilePage