// frontend/src/utils/leetcodeMastery.js
// Shared mapping from the backend's mastery labels (leetcode_mastery.py)
// to a 3-tier confidence badge, so every LeetCode component agrees on
// what "High/Medium/Low" means instead of each re-deriving it.

const TIER_BY_MASTERY = {
  'Not Practiced': 'low',
  'Introduced': 'low',
  'Some Practice': 'medium',
  'Consistent Practice': 'high',
  'Extensive Practice': 'high',
}

const DISPLAY_TIER_LABEL = { high: 'Mastered', medium: 'Growing', low: 'Weak' }

export function confidenceTier(mastery) {
  return TIER_BY_MASTERY[mastery] || 'medium'
}

export function confidenceLabel(tier) {
  if (tier === 'high') return 'High'
  if (tier === 'medium') return 'Medium'
  return 'Low'
}

export function formatRelativeTime(iso) {
  if (!iso) return null
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return null
  const diffMs = Date.now() - then
  const mins = Math.floor(diffMs / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} minute${mins === 1 ? '' : 's'} ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} day${days === 1 ? '' : 's'} ago`
  const months = Math.floor(days / 30)
  return `${months} month${months === 1 ? '' : 's'} ago`
}

export function tierDisplayLabel(tier) {
  return DISPLAY_TIER_LABEL[tier] || 'Growing'
}