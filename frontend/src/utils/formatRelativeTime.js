// frontend/src/utils/formatRelativeTime.js

export function formatRelativeTime(iso) {
  if (!iso) return 'never'
  const date = new Date(iso)
  const diffMs = Date.now() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays <= 0) {
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
    if (diffHours <= 0) {
      const diffMinutes = Math.max(1, Math.floor(diffMs / (1000 * 60)))
      return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`
    }
    return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`
  }
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return `${weeks} week${weeks === 1 ? '' : 's'} ago`
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export function formatDayLabel(iso) {
  if (!iso) return 'Unknown'
  const date = new Date(iso)
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.round((startOfDay(new Date()) - startOfDay(date)) / (1000 * 60 * 60 * 24))
  if (diffDays <= 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays} days ago`
  return 'Last week'
}