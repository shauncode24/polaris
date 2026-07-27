import { useMemo } from 'react'
import { useProfileData } from '../contexts/ProfileDataContext'

// Order matches BuildProfilePage's onboarding steps (1-5; step 6 is Review).
const STEPS = [
  { key: 'resume', label: 'Resume', sub: (r) => (r.resume ? 'Synced just now' : 'Not synced') },
  { key: 'github', label: 'GitHub', sub: (r) => (r.github ? `${r.github.summary?.repos_synced ?? 0} repos synced` : 'Not synced'), optional: true },
  { key: 'leetcode', label: 'LeetCode', sub: (r) => (r.leetcode ? 'Synced' : 'Not synced'), optional: true },
  { key: 'certificates', label: 'Certificates', sub: (r) => (r.certificates?.length ? `${r.certificates.length} added` : 'Optional'), optional: true },
  { key: 'goal', label: 'Goals', sub: (r) => (r.goal ? 'Set' : 'Not set') },
]

export function useProfileCompletion() {
  const { results } = useProfileData()

  return useMemo(() => {
    const checklist = STEPS.map((step) => ({
      ...step,
      done: Boolean(results[step.key] && (Array.isArray(results[step.key]) ? results[step.key].length > 0 : true)),
      subLabel: step.sub(results),
    }))

    const doneCount = checklist.filter((s) => s.done).length
    const percent = Math.round((doneCount / checklist.length) * 100)
    const firstIncompleteIndex = checklist.findIndex((s) => !s.done)
    const nextStep = firstIncompleteIndex === -1 ? checklist.length + 1 : firstIncompleteIndex + 1

    return { checklist, percent, nextStep, totalSteps: checklist.length + 1, isComplete: percent === 100 }
  }, [results])
}